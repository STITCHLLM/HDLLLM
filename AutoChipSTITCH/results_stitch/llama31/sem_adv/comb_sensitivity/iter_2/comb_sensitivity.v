module comb_sensitivity (
  input  wire a,
  input  wire b,
  input  wire c,
  input  wire sel,
  output reg out
);

always @(sel or a) begin
  if (sel == 1'b0)
    out <= a & b;
  else
    out <= b | c;
end

endmodule