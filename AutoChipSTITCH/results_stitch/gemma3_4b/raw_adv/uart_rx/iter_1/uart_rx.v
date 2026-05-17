module uart_rx (
  input clk,
  input rst,
  input rx,
  output reg [7:0] rx_data,
  output reg data_valid
);

  // Parameter definitions
  parameter CLKS_PER_BIT = 4;

  // Internal signals
  reg [7:0] bit_buffer;
  reg bit_count;
  reg byte_complete;
  reg state;

  // FSM states
  localparam IDLE = 0;
  localparam RECEIVING = 1;

  // Combinational logic for bit_count
  always @(posedge clk or negedge rst) begin
    if (!rst) begin
      bit_count <= 0;
    end else begin
      if (state == RECEIVING) begin
        bit_count <= CLKS_PER_BIT / 2;
      end else begin
        bit_count <= 0;
      end
    end
  end

  // Combinational logic for byte_complete
  always @(posedge clk or negedge rst) begin
    if (!rst) begin
      byte_complete <= 0;
    end else begin
      byte_complete <= (bit_count == CLKS_PER_BIT);
    end
  end

  // Combinational logic for state transition
  always @(posedge clk or negedge rst) begin
    if (!rst) begin
      state <= IDLE;
    end else begin
      case (state)
        IDLE: begin
          if (rx == 0) begin
            state <= RECEIVING;
          end
        end
        RECEIVING: begin
          if (bit_count == CLKS_PER_BIT) begin
            state <= IDLE;
            byte_complete <= 1;
            data_valid <= 1;
          end else begin
            bit_buffer[7-bit_count] <= rx;
            bit_count <= bit_count + 1;
          end
        end
        default: begin
          state <= IDLE;
        end
      endcase
    end
  end

  // Output logic
  always @(posedge clk or negedge rst) begin
    if (!rst) begin
      rx_data <= 0;
      data_valid <= 0;
    end else begin
      rx_data <= bit_buffer;
      data_valid <= byte_complete;
    end
  end

endmodule