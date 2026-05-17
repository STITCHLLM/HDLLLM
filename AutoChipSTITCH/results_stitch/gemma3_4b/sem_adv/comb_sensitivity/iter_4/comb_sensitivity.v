module comb_sensitivity (
  input a,
  input b,
  input c,
  input sel,
  output reg out
);

  always @(sel or a) begin
    default case : 0; // Default case for sel=0

    when (sel) begin
      out = a & b;
    end else begin
      out = a | b;
    end
  end
endmodule