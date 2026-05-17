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

  // FSM states
  typedef enum logic [1:0] {
    IDLE,
    RECEIVE_START,
    RECEIVE_DATA,
    RECEIVE_STOP
  } state_type;
  reg state, next_state;

  // State transition logic
  always @(*) begin
    next_state = state;
    case (state)
      IDLE: begin
        if (rx == 0) begin
          next_state = RECEIVE_START;
        end else begin
          next_state = IDLE;
        end
      end
      RECEIVE_START: begin
        next_state = RECEIVE_DATA;
      end
      RECEIVE_DATA: begin
        if (bit_count < CLKS_PER_BIT - 1) begin
          bit_buffer[7 - bit_count] = rx;
          bit_count = bit_count + 1;
          next_state = RECEIVE_DATA;
        end else begin
          next_state = RECEIVE_STOP;
        end
      end
      RECEIVE_STOP: begin
        if (rx == 0) begin
          next_state = IDLE;
          byte_complete = 1;
        end else begin
          next_state = RECEIVE_DATA;
        end
      end
      default: next_state = IDLE;
    endcase
  end

  // Sequential logic
  always @(posedge clk or negedge rst) begin
    if (!rst) begin
      state <= IDLE;
      bit_count <= 0;
      bit_buffer <= 0;
      rx_data <= 0;
      data_valid <= 0;
      byte_complete <= 0;
    end else begin
      state <= next_state;
      if (state == RECEIVE_DATA) begin
        bit_buffer[7 - bit_count] = rx;
        bit_count = bit_count + 1;
      end
    end
  end

  // Combinational logic for data_valid
  always @(posedge clk or negedge rst) begin
    if (!rst) begin
      data_valid <= 0;
    end else begin
      data_valid <= byte_complete;
    end
  end

  // Combinational logic for rx_data
  always @(posedge clk or negedge rst) begin
    if (!rst) begin
      rx_data <= 0;
    end else begin
      rx_data <= bit_buffer;
    end
  end

endmodule