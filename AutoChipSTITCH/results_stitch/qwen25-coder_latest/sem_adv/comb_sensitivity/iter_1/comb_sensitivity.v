module comb_sensitivity (
    input a,
    input b,
    input c,
    input sel,
    output reg out
);

always @(sel or a) begin
    if (sel == 1'b0)
        out = a & b;
    else
        out = b | c;
end

endmodule