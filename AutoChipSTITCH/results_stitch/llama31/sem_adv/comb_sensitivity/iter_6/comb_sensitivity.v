module comb_sensitivity (
  input  wire a,
  input  wire b,
  input  wire c,
  input  wire sel,
  output reg out
);

always @(sel or a) begin
  case (sel)
    1'b0: out <= a & b;
    default: out <= b | c;
  endcase
end

endmodule