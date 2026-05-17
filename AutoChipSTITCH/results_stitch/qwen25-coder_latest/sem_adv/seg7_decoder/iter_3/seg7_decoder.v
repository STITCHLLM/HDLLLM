module seg7_decoder (
    input [3:0] bcd,
    output reg [6:0] seg
);

always @(*) begin
    case (bcd)
        4'b0000: begin seg = 7'b0111111; end // 0
        4'b0001: begin seg = 7'b0000110; end // 1
        4'b0010: begin seg = 7'b1011011; end // 2
        4'b0011: begin seg = 7'b1001111; end // 3
        4'b0100: begin seg = 7'b1100110; end // 4
        4'b0101: begin seg = 7'b1101101; end // 5
        4'b0110: begin seg = 7'b1111101; end // 6
        4'b0111: begin seg = 7'b0000111; end // 7
        4'b1000: begin seg = 7'b1111111; end // 8
        4'b1001: begin seg = 7'b1101111; end // 9
        default: begin seg = 7'b1111111; end // Default case for invalid input (error state)
    endcase
end

endmodule