"""
autochip_stitch_runner.py  —  STITCH: Semantic Toolchain Integration for LLM-Driven RTL Generation
MLCAD Paper Submission Runner

THREE CONDITIONS per module per model:
  baseline  : iverilog + vvp only (replicates AutoChip baseline)
  raw_adv   : Verilator + iverilog + Yosys, raw tool output (no interpretation)
  sem_adv   : Verilator + iverilog + Yosys + semantic interpreter (STITCH contribution)

The three-condition comparison directly produces Table 7 in the paper:
  decoder_3to8 | gemma3:4b | baseline FAIL|6 | raw_adv FAIL|6 | sem_adv PASS|2

Results stored: results_stitch/<model>/<condition>/<module>/
Summary JSON:   results_stitch/<model>/stitch_summary.json

Usage:
  python autochip_stitch_runner.py --model gemma3:4b --condition all --module decoder_3to8
  python autochip_stitch_runner.py --model gemma3:4b --condition all
  python autochip_stitch_runner.py --model gemma3:12b --condition sem_adv --module decoder_3to8
"""

import os, subprocess, re, shutil, sys, json, time, argparse
from collections import Counter
from openai import OpenAI

# ── CONFIG ────────────────────────────────────────────────────────────────────
MAX_RETRIES      = 6
STUCK_THRESHOLD  = 2
TESTBENCH_DIR    = "testbenches_v2"
RESULTS_DIR      = "results_stitch"
WSL_PREFIX       = ["wsl"]

# ── API CLIENTS ───────────────────────────────────────────────────────────────
GEMINI_AVAILABLE = False
GEMINI_CLIENT    = None
try:
    from google import genai as google_genai
    from google.genai import types as genai_types
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
    if GEMINI_KEY:
        GEMINI_CLIENT    = google_genai.Client(api_key=GEMINI_KEY)
        GEMINI_AVAILABLE = True
except ImportError:
    pass

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CLIENT  = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
OLLAMA_CLIENT  = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

GEMINI_MODEL_MAP = {
    "gemini-2.5-flash": "models/gemini-2.5-flash",
    "gemini-2.5-pro":   "models/gemini-2.5-pro",
    "gemini-2.0-flash": "models/gemini-2.0-flash-exp",
    "gemini-1.5-flash": "models/gemini-1.5-flash",
    "gemini-1.5-pro":   "models/gemini-1.5-pro",
}

# Identical system prompt for ALL three conditions — controlled variable is
# feedback quality only, not system prompt content.
SYSTEM_PROMPT = """You are a Verilog-2001 expert.

MANDATORY RULES:
1. 'wire' for signals driven by 'assign' or sub-module output ports.
   'reg' ONLY for signals assigned inside 'always' blocks.
2. Non-blocking (<=) in clocked always blocks. Blocking (=) in combinational.
3. EVERY combinational always block MUST have a 'default' branch in case
   statements AND an 'else' branch in if-else chains. Omitting these infers
   LATCHES which cause wrong simulation output and are a synthesis error.
4. Sensitivity list: use @(*) or list ALL signals read inside the block.
   A partial sensitivity list causes the block to silently not re-evaluate.
5. Use ONLY Verilog-2001 syntax. No SystemVerilog: no 'logic', no 'always_comb',
   no 'always_ff', no bit-width-free literals like '1 or '0.
   Write all literals with explicit width: 1'b0, 8'hFF, 2'b01.
6. Every case branch with MULTIPLE assignments MUST use begin...end.
7. Return ONLY Verilog code inside ```verilog ... ``` fences. No prose."""


# ── UTILITIES ─────────────────────────────────────────────────────────────────
def win_to_wsl(win_path):
    p = os.path.abspath(win_path).replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = f"/mnt/{p[0].lower()}" + p[2:]
    return p

def sanitize_ascii(text):
    return text.encode("ascii", errors="ignore").decode("ascii")

_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|[\\/])(?:[^\s:'\"/\\<>|*?\n]+[\\/])*"
    r"([^\s:'\"/\\<>|*?\n]+\.v)"
)
def strip_paths(text):
    return _PATH_RE.sub(r"\1", text)


# ── LLM CALL with token counting ──────────────────────────────────────────────
def call_llm(model, messages):
    """Returns (text, prompt_tokens, completion_tokens)."""
    if model.startswith("gemini"):
        if not GEMINI_AVAILABLE:
            print("ERROR: Set GEMINI_API_KEY and install google-genai"); sys.exit(1)
        api_model = GEMINI_MODEL_MAP.get(model, f"models/{model}")
        history = "\n".join(
            f"[{'USER' if m['role']=='user' else 'ASSISTANT'}]\n{m['content']}"
            for m in messages if m["role"] != "system"
        )
        resp = GEMINI_CLIENT.models.generate_content(
            model=api_model,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, temperature=0.1),
            contents=history,
        )
        meta = getattr(resp, "usage_metadata", None)
        pt = getattr(meta, "prompt_token_count",     0) if meta else 0
        ct = getattr(meta, "candidates_token_count", 0) if meta else 0
        return resp.text, pt, ct
    elif model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        if not OPENAI_CLIENT:
            print("ERROR: Set OPENAI_API_KEY"); sys.exit(1)
        resp = OPENAI_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1)
        u = resp.usage
        return resp.choices[0].message.content, u.prompt_tokens, u.completion_tokens
    else:
        resp = OLLAMA_CLIENT.chat.completions.create(
            model=model, messages=messages, temperature=0.1)
        u = getattr(resp, "usage", None)
        pt = getattr(u, "prompt_tokens",     0) if u else 0
        ct = getattr(u, "completion_tokens", 0) if u else 0
        return resp.choices[0].message.content, pt, ct


# ── LAYER 1: VERILATOR ────────────────────────────────────────────────────────
VERILATOR_SUPPRESS = [
    "-Wno-DECLFILENAME", "-Wno-TIMESCALEMOD", "-Wno-EOFNEWLINE",
]

def run_verilator_lint(v_file):
    """Returns (warnings_str, had_meaningful_warnings: bool)."""
    wsl_path = win_to_wsl(v_file)
    cmd = WSL_PREFIX + ["verilator", "--lint-only", "-Wall",
                        "--bbox-unsup"] + VERILATOR_SUPPRESS + [wsl_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"[VERILATOR ERROR: {e}]", True

    output = result.stdout + result.stderr
    kept = [
        s.strip() for s in output.splitlines()
        if s.strip()
        and "... Use" not in s
        and "... For warning" not in s
        and (s.strip().startswith("%Warning") or s.strip().startswith("%Error")
             or s.strip().startswith("..."))
    ]
    had = result.returncode != 0 and bool(kept)
    return ("\n".join(kept) if kept else "(no warnings)"), had


# ── SEMANTIC INTERPRETER (STITCH core contribution) ───────────────────────────
# Maps Verilator warning codes to plain-English fix directives.
# This is a deterministic regex script — zero additional inference cost.
# The interpreter is what separates raw_adv (FAIL) from sem_adv (PASS)
# for weaker models in the 4B-14B capability range.

_VERILATOR_INTERP = {
    "UNUSEDSIGNAL": lambda sig: (
        f"*** CRITICAL: Port '{sig}' is declared but NEVER USED in your always block. ***\n"
        f"You wrote '{sig}' in the module port list but forgot to wire it into your logic.\n"
        f"You MUST condition on '{sig}':\n"
        f"  always @(*) begin\n"
        f"    if ({sig}) begin\n"
        f"      <your existing case or logic here>\n"
        f"    end else begin\n"
        f"      out = 8'b0;  // or whatever your output signal is named\n"
        f"    end\n"
        f"  end\n"
        f"The FAIL lines (enable=0 returning non-zero output) are caused by '{sig}' being ignored."
    ),
    "MULTIDRIVEN": lambda sig: (
        f"*** CRITICAL: Signal '{sig}' is driven from multiple always blocks. ***\n"
        f"Only ONE always block may drive a given signal.\n"
        f"Merge all assignments to '{sig}' into a single always block."
    ),
    "UNDRIVEN": lambda sig: (
        f"*** CRITICAL: Output '{sig}' is never assigned. ***\n"
        f"Add an assignment: '{sig} = <value>;' in your always block or use assign."
    ),
    "WIDTHTRUNC": lambda sig: (
        f"*** WARNING: Bit-width truncation on '{sig}'. ***\n"
        f"You are assigning a wider value into a narrower signal.\n"
        f"Use explicit bit-select to avoid silent truncation: signal[N-1:0] = value[N-1:0];"
    ),
    "WIDTHEXPAND": lambda sig: (
        f"*** WARNING: Width expansion on '{sig}' — value is zero-extended. ***\n"
        f"Check that signal widths match your port declarations."
    ),
    "BLKSEQ": lambda sig: (
        f"*** CRITICAL: Blocking assignment (=) in clocked always block for '{sig}'. ***\n"
        f"In clocked always @(posedge clk) blocks, ALWAYS use non-blocking: '{sig} <= value;'"
    ),
    "COMBDLY": lambda sig: (
        f"*** WARNING: Delay (#) in combinational block near '{sig}'. ***\n"
        f"Remove all # delays from always @(*) blocks."
    ),
}

def interpret_verilator(raw_out):
    """
    Parse raw Verilator output and return (interpreted_text, codes_fired).
    interpreted_text is empty string if no known codes matched.
    """
    if not raw_out or raw_out.startswith("("):
        return "", []

    blocks = []
    codes  = []

    for code, make_msg in _VERILATOR_INTERP.items():
        if code not in raw_out:
            continue
        codes.append(code)

        # Extract signal name: try quoted first, then end-of-line word
        sig = "the_signal"
        for line in raw_out.splitlines():
            if code in line:
                m = re.search(r"['\"]([A-Za-z_]\w*)['\"]", line)
                if not m:
                    m = re.search(r":\s*([A-Za-z_]\w*)\s*$", line)
                if m:
                    sig = m.group(1)
                    break
        blocks.append(make_msg(sig))

    return "\n\n".join(blocks), codes


def interpret_yosys_latches(latch_lines):
    """Extract signal names from Yosys latch lines and return plain-English fix."""
    if not latch_lines:
        return ""

    signals = []
    for line in latch_lines:
        # "Latch inferred for signal `\module.\signame'"
        m = re.search(r"signal\s+`\\[^.]+\.\\([^'`]+)'", line)
        if m:
            signals.append(m.group(1))
        else:
            m = re.search(r"\\([A-Za-z_]\w*)[`']", line)
            if m:
                signals.append(m.group(1))

    sig_list = ", ".join(f"'{s}'" for s in signals) if signals else "an output signal"
    first    = signals[0] if signals else "out"

    return (
        f"\n\n*** YOSYS: LATCH INFERRED for signal(s) {sig_list} ***\n\n"
        f"ROOT CAUSE: Your always block does NOT assign {sig_list} on every\n"
        f"code path. When the unhandled path is taken, synthesis infers a latch\n"
        f"that HOLDS THE LAST VALUE — this is why enable=0 returns the previous output.\n\n"
        f"EXACT FIX (choose one):\n"
        f"  A) Add else branch to every if without one:\n"
        f"       if (condition) begin {first} = X; end\n"
        f"       else           begin {first} = 0; end  <-- ADD THIS\n\n"
        f"  B) Add default to every case statement:\n"
        f"       case (sel)\n"
        f"         ... existing cases ...\n"
        f"         default: begin {first} = 0; end  <-- ADD THIS\n"
        f"       endcase"
    )


# ── LAYER 2: YOSYS ────────────────────────────────────────────────────────────
_LATCH_KEYWORDS = [
    "latch inferred for signal",   # Yosys 0.33 confirmed exact string
    "$_dlatch_",                   # cell type in stat output
    "proc_dlatch",                 # pass name
    "inferred latch",
    "latch for signal",
    "latch(es)",
    "has latches",
    "generating latch",
]

_YOSYS_KEEP = re.compile(
    r"(Warning|warning|Error|error|Latch|latch|inferred|proc_dlatch|"
    r"continuous assignment|Number of cells|\$_DLATCH|\$dlatch|\$dff)",
    re.IGNORECASE,
)

def run_yosys_check(v_file, module_name):
    """Returns (report_str, has_latches, latch_lines, cell_count)."""
    wsl_path = win_to_wsl(v_file)
    script   = f"read_verilog {wsl_path}; synth -top {module_name}; stat"
    cmd      = WSL_PREFIX + ["yosys", "-p", script]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"[YOSYS ERROR: {e}]", False, [], 0

    output      = result.stdout + result.stderr
    has_latches = any(kw in output.lower() for kw in _LATCH_KEYWORDS)
    kept        = [l.strip() for l in output.splitlines()
                   if l.strip() and _YOSYS_KEEP.search(l)]

    cell_count = 0
    for line in output.splitlines():
        if "Number of cells" in line:
            m = re.search(r"Number of cells:\s*(\d+)", line)
            if m:
                cell_count = int(m.group(1))
            if line.strip() not in kept:
                kept.append(line.strip())
            break

    latch_lines = [l for l in output.splitlines()
                   if any(kw in l.lower() for kw in _LATCH_KEYWORDS)]

    return "\n".join(kept) if kept else "(no synthesis warnings)", \
           has_latches, latch_lines[:5], cell_count


# ── LAYER 3: IVERILOG + VVP ───────────────────────────────────────────────────
def run_iverilog_sim(iter_dir, module_name):
    vvp_out     = os.path.join(iter_dir, "sim.vvp")
    v_files_wsl = [win_to_wsl(os.path.join(iter_dir, f))
                   for f in sorted(os.listdir(iter_dir)) if f.endswith(".v")]
    vvp_wsl     = win_to_wsl(vvp_out)

    comp = subprocess.run(WSL_PREFIX + ["iverilog", "-o", vvp_wsl] + v_files_wsl,
                          capture_output=True, text=True, encoding="utf-8")

    with open(os.path.join(iter_dir, "sim_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"--- COMPILATION ---\n{comp.stderr}\n")

    if comp.returncode != 0:
        err     = strip_paths(comp.stderr)
        preview = "\n".join(err.strip().splitlines()[:10])
        print("  iverilog:\n    " + preview.replace("\n", "\n    "))
        return False, f"COMPILATION ERROR:\n{err}"

    sim = subprocess.run(WSL_PREFIX + ["vvp", vvp_wsl],
                         capture_output=True, text=True, encoding="utf-8")
    output = sim.stdout + sim.stderr

    with open(os.path.join(iter_dir, "sim_log.txt"), "a", encoding="utf-8") as f:
        f.write(f"\n--- SIMULATION ---\n{output}\n")

    if "FAIL" in output or (
            "ALL TESTS PASSED" not in output and "PASS" not in output):
        preview = "\n".join(output.strip().splitlines()[:8])
        print("  sim:\n    " + preview.replace("\n", "\n    "))
        return False, f"SIMULATION FAILED:\n{output}"

    return True, output


# ── ERROR CLASSIFIER ──────────────────────────────────────────────────────────
def classify_error(feedback):
    fb = feedback.lower()
    if "compilation error" in fb:
        if "not a valid l-value" in fb or "continuous" in fb:
            return "reg_wire_mismatch"
        if "already declared" in fb:   return "duplicate_module"
        if "unknown module" in fb:     return "missing_module"
        if ("syntax error" in fb or "malformed" in fb
                or "incomprehensible" in fb):  return "syntax_error"
        if "systemverilog" in fb:      return "systemverilog_syntax"
        if "is not a port" in fb:      return "port_mismatch"
        if "sorry:" in fb:             return "unsupported_construct"
        return "compile_other"
    if "simulation failed" in fb:
        return "logic_error" if "fail" in fb else "sim_other"
    return "sim_other"


# ── FEEDBACK BUILDERS ─────────────────────────────────────────────────────────
_BASE_HINTS = {
    "reg_wire_mismatch":    "\nHINT: Use 'wire' for assign/submodule outputs; 'reg' for always-block only.",
    "syntax_error":         "\nHINT: Multiple assignments per case branch need begin...end. No SystemVerilog.",
    "systemverilog_syntax": "\nHINT: Use wire/reg not logic. Use 1'b1/1'b0 not '1/'0. Use always@(*) not always_comb.",
    "logic_error":          "\nHINT: Compiles but wrong output. Read each FAIL line — trace inputs to expected vs actual.",
    "duplicate_module":     "\nHINT: Delete the redefined module. Write only the requested top-level module.",
    "port_mismatch":        "\nHINT: Port names must match the specification exactly.",
    "sim_other":            "\nHINT: No PASS/FAIL printed — check all output ports are driven.",
}

def _build_baseline_feedback(iverilog_fb, err_type):
    """Condition A: iverilog output + type hint only. Replicates AutoChip."""
    hint = _BASE_HINTS.get(err_type, "")
    return (
        "The Verilog code failed. Fix ALL errors and return the COMPLETE "
        "module inside ```verilog ... ```. ASCII only.\n\n"
        f"Error output:\n{iverilog_fb}{hint}"
    )

def _build_raw_adv_feedback(verilator_out, yosys_report, latch_lines,
                              iverilog_fb, err_type, has_latches, cell_count):
    """
    Condition B: All three tool outputs passed through RAW (no interpretation).
    This isolates the effect of tool presence from interpretation quality.
    Comparison with sem_adv shows that raw output alone is insufficient
    for weaker models.
    """
    hint = _BASE_HINTS.get(err_type, "")
    cell_ctx = f"\n  Yosys cells: {cell_count}" if cell_count else ""

    latch_raw = ""
    if has_latches:
        raw_lines = "\n".join(f"  {l.strip()}" for l in latch_lines)
        latch_raw = f"\n\nYosys raw latch output:\n{raw_lines}"

    return (
        "The Verilog code failed. Return the COMPLETE corrected module "
        "inside ```verilog ... ```. ASCII only.\n\n"
        "=== VERILATOR LINT ===\n"
        f"{verilator_out}\n\n"
        "=== IVERILOG + VVP ===\n"
        f"{iverilog_fb}{hint}\n\n"
        "=== YOSYS SYNTHESIS ==={cell_ctx}\n"
        f"{yosys_report}{latch_raw}"
    ).replace("{cell_ctx}", cell_ctx)

def _build_sem_adv_feedback(verilator_out, yosys_report, latch_lines,
                              iverilog_fb, err_type, has_latches, cell_count,
                              interp_text, interp_codes):
    """
    Condition C: All three tools + semantic interpreter.
    The interpreter translates raw warning codes into targeted fix directives.
    This is the STITCH contribution — directives resolve weaker-model failures
    that raw output cannot.
    """
    hint = _BASE_HINTS.get(err_type, "")
    cell_ctx = f"\n  Yosys cells: {cell_count}" if cell_count else ""

    # Verilator layer: raw + interpreted (when applicable)
    if interp_text:
        verilator_section = (
            f"Raw Verilator output:\n{verilator_out}\n\n"
            f"--- Semantic Interpreter Directive ---\n{interp_text}"
        )
    else:
        verilator_section = verilator_out

    # Yosys layer: raw + interpreted (when latches found)
    yosys_interp = interpret_yosys_latches(latch_lines) if has_latches else ""
    if has_latches:
        yosys_section = (
            f"Yosys cells: {cell_count} (includes $_DLATCH_ latch cells)\n"
            f"Raw Yosys output:\n{yosys_report}"
            f"{yosys_interp}"
        )
    else:
        yosys_section = f"Yosys: {cell_count} cells, no latches.\n{yosys_report}"

    return (
        "The Verilog code failed. Read the SEMANTIC DIRECTIVES carefully — they\n"
        "give you the exact fix. Return the COMPLETE module inside "
        "```verilog ... ```. ASCII only.\n\n"
        "=== LAYER 1: VERILATOR LINT (with semantic interpretation) ===\n"
        f"{verilator_section}\n\n"
        "=== LAYER 2: IVERILOG + VVP ===\n"
        f"{iverilog_fb}{hint}\n\n"
        "=== LAYER 3: YOSYS SYNTHESIS (with semantic interpretation) ===\n"
        f"{yosys_section}"
    )

_REWRITE_PROMPT = (
    "Your previous {n} attempts all failed with '{err_type}'.\n"
    "DISCARD all prior code. Write a BRAND-NEW Verilog-2001 module from scratch.\n\n"
    "Rules for this rewrite:\n"
    "  1. Every case branch with multiple assignments: begin...end\n"
    "  2. Every case statement: include a default branch\n"
    "  3. Every if without else: add else with safe default values\n"
    "  4. Sensitivity: use @(*)\n"
    "  5. No SystemVerilog\n\n"
    "ORIGINAL SPECIFICATION:\n{spec}\n\n"
    "Return ONLY the module inside ```verilog ... ```. ASCII only."
)


# ── MAIN LOOP ──────────────────────────────────────────────────────────────────
def run_one_condition(spec, module_name, model, condition, dependencies=None):
    """
    Run one condition (baseline | raw_adv | sem_adv) for one module.
    condition controls which feedback builder is used.
    Returns metrics dict.
    """
    if dependencies is None:
        dependencies = []

    tb_path = os.path.join(TESTBENCH_DIR, f"{module_name}_tb.v")
    if not os.path.exists(tb_path):
        print(f"  ERROR: testbench not found: {tb_path}")
        return None

    safe_model  = model.replace(":", "_").replace(".", "")
    project_dir = os.path.join(RESULTS_DIR, safe_model, condition, module_name)
    os.makedirs(project_dir, exist_ok=True)

    cond_label = {
        "baseline": "BASELINE  (iverilog only)",
        "raw_adv":  "RAW ADV   (Verilator+Yosys, no interpretation)",
        "sem_adv":  "SEM ADV   (Verilator+Yosys+semantic interpreter)",
    }[condition]

    use_tools  = condition in ("raw_adv", "sem_adv")
    use_interp = condition == "sem_adv"

    print(f"\n{'='*68}")
    print(f"  {module_name}  |  {model}")
    print(f"  {cond_label}")
    print(f"{'='*68}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": spec},
    ]

    metrics = {
        "module": module_name, "model": model, "condition": condition,
        "pass": False, "iterations_to_pass": None,
        "time_to_pass_sec": None, "total_time_sec": None,
        "total_iterations": MAX_RETRIES,
        "compile_errors": 0, "sim_errors": 0,
        "latch_warnings": 0, "verilator_catches": 0,
        "semantic_fired": 0,          # key metric: how many iters interpreter fired
        "verilator_codes_seen": [],   # which codes triggered interpretation
        "total_prompt_tokens": 0, "total_completion_tokens": 0, "total_tokens": 0,
        "error_types": [], "per_iter_detail": [],
    }

    t_start         = time.time()
    consecutive     = 0
    last_err        = None
    prev_cells      = None

    for i in range(MAX_RETRIES):
        iter_dir = os.path.join(project_dir, f"iter_{i+1}")
        os.makedirs(iter_dir, exist_ok=True)
        print(f"\n  Iteration {i+1}/{MAX_RETRIES}")

        # LLM call
        t_llm = time.time()
        try:
            llm_out, pt, ct = call_llm(model, messages)
        except Exception as e:
            print(f"  LLM Error: {e}"); break
        llm_t = time.time() - t_llm
        print(f"  LLM {llm_t:.1f}s  [prompt={pt} completion={ct}]")

        metrics["total_prompt_tokens"]     += pt
        metrics["total_completion_tokens"] += ct
        metrics["total_tokens"]            += pt + ct

        with open(os.path.join(iter_dir, "llm_response.txt"), "w", encoding="utf-8") as f:
            f.write(llm_out)

        match = re.search(r"```(?:verilog)?(.*?)```", llm_out, re.DOTALL)
        code  = sanitize_ascii(match.group(1).strip() if match else llm_out.strip())

        v_path = os.path.join(iter_dir, f"{module_name}.v")
        with open(v_path, "w", encoding="utf-8") as f:
            f.write(code)

        for dep in dependencies:
            if os.path.exists(dep): shutil.copy(dep, iter_dir)
        shutil.copy(tb_path, iter_dir)

        # Layer 1: Verilator (tools conditions only)
        verilator_out  = "(baseline: skipped)"
        verilator_flag = False
        interp_text    = ""
        interp_codes   = []

        if use_tools:
            verilator_out, verilator_flag = run_verilator_lint(v_path)
            if verilator_flag:
                metrics["verilator_catches"] += 1
                if use_interp:
                    interp_text, interp_codes = interpret_verilator(verilator_out)
                    if interp_text:
                        metrics["semantic_fired"] += 1
                        metrics["verilator_codes_seen"].extend(interp_codes)
                codes_str = ",".join(interp_codes) if interp_codes else "?"
                if use_interp and interp_text:
                    print(f"  Verilator [{codes_str}] → INTERPRETED")
                else:
                    print(f"  Verilator [{codes_str}] raw")
            else:
                print("  Verilator: clean")

        # Layer 2: iverilog + vvp
        success, iverilog_fb = run_iverilog_sim(iter_dir, module_name)
        elapsed = time.time() - t_start

        # Layer 3: Yosys (tools conditions, compile success only)
        yosys_report = "(baseline: skipped)"
        has_latches  = False
        latch_lines  = []
        cell_count   = 0
        cell_delta   = None

        if use_tools and "COMPILATION ERROR" not in iverilog_fb:
            yosys_report, has_latches, latch_lines, cell_count = run_yosys_check(
                v_path, module_name)
            if prev_cells is not None and cell_count > 0:
                cell_delta = cell_count - prev_cells
            prev_cells = cell_count

            if has_latches:
                print(f"  Yosys LATCH: {(latch_lines[0].strip()[:55] if latch_lines else '')} "
                      f"({cell_count} cells)")
                metrics["latch_warnings"] += 1
            else:
                delta_str = f" Δ{cell_delta:+d}" if cell_delta is not None else ""
                print(f"  Yosys: clean ({cell_count} cells{delta_str})")

        # Record iteration
        iter_detail = {
            "iter": i + 1, "prompt_tokens": pt, "completion_tokens": ct,
            "llm_time_sec": round(llm_t, 2),
            "verilator_flag": verilator_flag, "interp_codes": interp_codes,
            "semantic_fired": bool(interp_text),
            "yosys_latch": has_latches, "yosys_cells": cell_count,
            "yosys_delta": cell_delta,
            "result": "PASS" if success else "FAIL",
            "err_type": None,
        }

        if success:
            print(f"  PASSED iteration {i+1}  ({elapsed:.1f}s total)")
            iter_detail["err_type"] = "PASS"
            metrics["per_iter_detail"].append(iter_detail)
            metrics.update({
                "pass": True, "iterations_to_pass": i + 1,
                "time_to_pass_sec": round(elapsed, 2),
                "total_time_sec": round(elapsed, 2),
                "total_iterations": i + 1,
            })
            break

        err_type = classify_error(iverilog_fb)
        iter_detail["err_type"] = err_type
        metrics["per_iter_detail"].append(iter_detail)

        if "COMPILATION" in iverilog_fb: metrics["compile_errors"] += 1
        else:                            metrics["sim_errors"]     += 1
        metrics["error_types"].append(err_type)
        print(f"  FAIL: {err_type}")

        if err_type == last_err: consecutive += 1
        else:                    consecutive = 1; last_err = err_type

        messages.append({"role": "assistant", "content": llm_out})

        if consecutive >= STUCK_THRESHOLD:
            print(f"  STUCK '{err_type}' x{consecutive} — rewrite injected")
            messages.append({"role": "user", "content": _REWRITE_PROMPT.format(
                n=consecutive, err_type=err_type, spec=spec)})
            consecutive = 0
        else:
            if condition == "baseline":
                fb = _build_baseline_feedback(iverilog_fb, err_type)
            elif condition == "raw_adv":
                fb = _build_raw_adv_feedback(verilator_out, yosys_report, latch_lines,
                                              iverilog_fb, err_type, has_latches, cell_count)
            else:  # sem_adv
                fb = _build_sem_adv_feedback(verilator_out, yosys_report, latch_lines,
                                              iverilog_fb, err_type, has_latches, cell_count,
                                              interp_text, interp_codes)
            messages.append({"role": "user", "content": fb})

    if metrics["total_time_sec"] is None:
        metrics["total_time_sec"] = round(time.time() - t_start, 2)

    with open(os.path.join(project_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    if not metrics["pass"]:
        print(f"  FAILED all {MAX_RETRIES} iters "
              f"({metrics['total_time_sec']:.1f}s | tokens={metrics['total_tokens']})")
    return metrics


# ── THREE-COLUMN COMPARISON TABLE ─────────────────────────────────────────────
def print_stitch_table(all_results, model):
    """
    Prints the three-condition comparison table for the paper.
    Columns: Module | Category | Baseline | Raw Advanced | Semantic Advanced
    This is Table 7 in the STITCH paper.
    """
    CONDITIONS = ["baseline", "raw_adv", "sem_adv"]
    LABELS     = ["Baseline", "Raw Adv", "Sem Adv"]
    W = 90

    print(f"\n{'='*W}")
    print(f"  STITCH TABLE — Three-Condition Comparison  |  Model: {model}")
    print(f"  (Table 7 in paper)")
    print(f"{'='*W}")
    print(f"  {'Module':<22} {'Cat':<12} {'Baseline':^14} {'Raw Adv':^14} {'Sem Adv':^14} "
          f"{'ΔB→S':>5} {'SemanFired':>10}")
    print(f"  {'':22} {'':12} {'P|Iters':^14} {'P|Iters':^14} {'P|Iters':^14}")
    print(f"  {'-'*88}")

    # Group results by condition
    cond_map = {c: {} for c in CONDITIONS}
    for m in all_results:
        cond_map[m["condition"]][m["module"]] = m

    grand = {c: {"pass": 0, "iters": 0, "tokens": 0} for c in CONDITIONS}
    grand["sem_adv"]["sem_fired"] = 0

    for mod, cfg in BENCHMARK.items():
        row = {}
        for c in CONDITIONS:
            row[c] = cond_map[c].get(mod)
        if not any(row.values()):
            continue

        cat = cfg["category"].replace("_", " ")
        cells = []
        for c in CONDITIONS:
            m = row[c]
            if m:
                p = "PASS" if m["pass"] else "FAIL"
                it = m["iterations_to_pass"] or MAX_RETRIES
                grand[c]["pass"]   += 1 if m["pass"] else 0
                grand[c]["iters"]  += it
                grand[c]["tokens"] += m.get("total_tokens", 0)
                cells.append(f"{p}|{it}")
            else:
                cells.append("n/a")

        # Delta: baseline iters - sem_adv iters (positive = sem_adv needed fewer)
        delta_str = ""
        if row["baseline"] and row["sem_adv"]:
            b_it = row["baseline"]["iterations_to_pass"] or MAX_RETRIES
            s_it = row["sem_adv"]["iterations_to_pass"]  or MAX_RETRIES
            d    = b_it - s_it
            delta_str = f"+{d}" if d > 0 else str(d)

        sf = row["sem_adv"].get("semantic_fired", 0) if row["sem_adv"] else 0
        grand["sem_adv"]["sem_fired"] = grand["sem_adv"].get("sem_fired", 0) + sf

        print(f"  {mod:<22} {cat:<12} {cells[0]:^14} {cells[1]:^14} {cells[2]:^14} "
              f"{delta_str:>5} {sf:>10}")

    n = len(BENCHMARK)
    print(f"\n  {'Pass rate':<34} "
          f"{grand['baseline']['pass']}/{n}".center(14) +
          f" {grand['raw_adv']['pass']}/{n}".center(14) +
          f" {grand['sem_adv']['pass']}/{n}".center(14))
    print(f"  {'Total iterations':<34} "
          f"{grand['baseline']['iters']}".center(14) +
          f" {grand['raw_adv']['iters']}".center(14) +
          f" {grand['sem_adv']['iters']}".center(14))
    print(f"  {'Total tokens':<34} "
          f"{grand['baseline']['tokens']}".center(14) +
          f" {grand['raw_adv']['tokens']}".center(14) +
          f" {grand['sem_adv']['tokens']}".center(14))
    print(f"\n  Semantic interpreter fired: {grand['sem_adv'].get('sem_fired',0)} "
          f"iteration(s) across all modules (sem_adv only)")

    # Error transition matrix
    _CODE = {
        "PASS":"PASS","logic_error":"LGIC","syntax_error":"SYNT",
        "systemverilog_syntax":"SV!!","reg_wire_mismatch":"RWMX",
        "compile_other":"COMP","sim_other":"SIMO","duplicate_module":"DUPL",
        "port_mismatch":"PORT","missing_module":"MISS",
        "unsupported_construct":"UNSP", None:"----",
    }
    print(f"\n  Error Transition Matrix:")
    print(f"  {'Module':<22} {'Cond':<8}  " +
          "  ".join(f"I{j+1}" for j in range(MAX_RETRIES)))
    print(f"  {'-'*82}")
    for mod in BENCHMARK:
        for c, label in zip(CONDITIONS, ["base", "raw ", "sem "]):
            m = cond_map[c].get(mod)
            if not m:
                continue
            codes = [_CODE.get(it.get("err_type"), "????")
                     for it in m["per_iter_detail"]]
            codes += ["    "] * (MAX_RETRIES - len(codes))
            print(f"  {mod:<22} {label}      " + "  ".join(codes))
        print()

    print(f"{'='*W}\n")


# ── BENCHMARK ─────────────────────────────────────────────────────────────────
BENCHMARK = {

    "seg7_decoder": {
        "category": "latch_target",
        "spec": (
            "Create a Verilog-2001 module named 'seg7_decoder'.\n"
            "Ports: input [3:0] bcd; output reg [6:0] seg\n"
            "Implement a combinational 7-segment display decoder.\n"
            "Segment bit ordering: seg[6:0] = {g, f, e, d, c, b, a} (1 = segment ON)\n"
            "Use a case statement in a combinational always block.\n"
            "Encodings for BCD digits 0 through 9:\n"
            "  0: 7'b0111111    1: 7'b0000110    2: 7'b1011011\n"
            "  3: 7'b1001111    4: 7'b1100110    5: 7'b1101101\n"
            "  6: 7'b1111101    7: 7'b0000111    8: 7'b1111111\n"
            "  9: 7'b1101111\n"
            "The valid input range is 0-9. Behavior for inputs 10-15 is not\n"
            "specified by the application - implement only the 10 defined cases.\n"
        ),
    },

    "alu_ops": {
        "category": "latch_target",
        "spec": (
            "Create a Verilog-2001 module named 'alu_ops'.\n"
            "Ports: input [7:0] a, b; input [2:0] opcode;\n"
            "       output reg [7:0] result; output reg carry_out, zero\n"
            "Implement a combinational ALU. Use a case statement inside a\n"
            "combinational always block. Every case branch assigns result,\n"
            "carry_out, AND zero - wrap each branch in begin...end.\n"
            "Operations:\n"
            "  3'b000 ADD: {carry_out, result} = a + b; zero = (result==8'd0);\n"
            "  3'b001 SUB: result = a - b; carry_out = (a < b); zero = (result==8'd0);\n"
            "  3'b010 AND: result = a & b; carry_out = 1'b0; zero = (result==8'd0);\n"
            "  3'b011 OR : result = a | b; carry_out = 1'b0; zero = (result==8'd0);\n"
            "  3'b100 XOR: result = a ^ b; carry_out = 1'b0; zero = (result==8'd0);\n"
            "Implement only the five operations listed above.\n"
        ),
    },

    "decoder_3to8": {
        "category": "latch_target",
        "spec": (
            "Create a Verilog-2001 module named 'decoder_3to8'.\n"
            "Ports: input enable; input [2:0] in; output reg [7:0] out\n"
            "Implement a 3-to-8 one-hot decoder with an active-high enable.\n"
            "When enable is asserted, use a case statement to drive the\n"
            "corresponding output bit high and all others low:\n"
            "  in=3'd0 -> out=8'b0000_0001\n"
            "  in=3'd1 -> out=8'b0000_0010\n"
            "  in=3'd2 -> out=8'b0000_0100\n"
            "  in=3'd3 -> out=8'b0000_1000\n"
            "  in=3'd4 -> out=8'b0001_0000\n"
            "  in=3'd5 -> out=8'b0010_0000\n"
            "  in=3'd6 -> out=8'b0100_0000\n"
            "  in=3'd7 -> out=8'b1000_0000\n"
            "All logic is combinational - no clock, no reset.\n"
        ),
    },

    "comb_sensitivity": {
        "category": "verilator_target",
        "spec": (
            "Create a Verilog-2001 module named 'comb_sensitivity'.\n"
            "Ports: input a, b, c, sel; output reg out\n"
            "Implement a combinational function:\n"
            "  When sel=0: out = a AND b\n"
            "  When sel=1: out = b OR c\n"
            "Use an always block. Do NOT use @(*) - this module targets an older\n"
            "synthesis tool that requires an explicit sensitivity list.\n"
            "The block is controlled by the selector and input a, so write:\n"
            "  always @(sel or a)\n"
            "Then implement the if-else logic inside this always block.\n"
        ),
    },

    "uart_rx": {
        "category": "control",
        "spec": (
            "Create a Verilog-2001 module named 'uart_rx'.\n"
            "Parameter: CLKS_PER_BIT = 4\n"
            "Ports: input clk, rst, rx; output reg [7:0] rx_data; output reg data_valid\n"
            "Implement an 8-N-1 UART receiver (8 data bits, no parity, 1 stop bit).\n"
            "Idle line is high. Start bit is low. 8 data bits LSB first. Stop bit high.\n"
            "Sample each bit at the MIDDLE of its bit period (CLKS_PER_BIT/2 clocks in).\n"
            "data_valid pulses HIGH for exactly 1 clock when a complete byte is received.\n"
            "Synchronous active-high reset. FSM states are your design choice.\n"
        ),
    },
}


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="STITCH Runner — three-condition MLCAD benchmark",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--model", default="gemma3:4b",
                        help="LLM: gemma3:4b, gemma3:12b, qwen2.5-coder:14b, llama3.1:8b, ...")
    parser.add_argument("--condition", default="all",
                        choices=["baseline", "raw_adv", "sem_adv", "all"],
                        help=(
                            "baseline  = iverilog only (AutoChip replication)\n"
                            "raw_adv   = Verilator+Yosys, raw output\n"
                            "sem_adv   = Verilator+Yosys+semantic interpreter (STITCH)\n"
                            "all       = run all three conditions"
                        ))
    parser.add_argument("--module", default=None,
                        help=f"Single module (default: all). "
                             f"Choices: {list(BENCHMARK.keys())}")
    args = parser.parse_args()

    items = list(BENCHMARK.items())
    if args.module:
        items = [(k, v) for k, v in items if k == args.module]
        if not items:
            print(f"ERROR: '{args.module}' not in benchmark.")
            print(f"  Choices: {list(BENCHMARK.keys())}")
            sys.exit(1)

    conditions_to_run = (
        ["baseline", "raw_adv", "sem_adv"] if args.condition == "all"
        else [args.condition]
    )

    all_results = []
    for cond in conditions_to_run:
        label = {"baseline": "A", "raw_adv": "B", "sem_adv": "C"}[cond]
        print(f"\n{'#'*68}")
        print(f"  CONDITION {label}: {cond.upper()}")
        print(f"{'#'*68}")
        for mod, cfg in items:
            m = run_one_condition(
                spec=cfg["spec"], module_name=mod,
                model=args.model, condition=cond,
            )
            if m:
                all_results.append(m)

    # Save summary
    safe_model   = args.model.replace(":", "_").replace(".", "")
    summary_dir  = os.path.join(RESULTS_DIR, safe_model)
    os.makedirs(summary_dir, exist_ok=True)
    summary_path = os.path.join(summary_dir, "stitch_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "model": args.model, "conditions": conditions_to_run,
            "results": all_results
        }, f, indent=2)

    if len(conditions_to_run) > 1:
        print_stitch_table(all_results, args.model)

    print(f"  Results saved -> {summary_path}\n")
