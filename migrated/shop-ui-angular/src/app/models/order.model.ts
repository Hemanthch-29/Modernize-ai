export interface OrderItem {
  productName: string;
  quantity: number;
  unitPrice: number;
}

export interface Order {
  orderId: number;
  customerName: string;
  status: string;
  total: number;
  items: OrderItem[];
}

export interface OrderSummary {
  orderId: number;
  status: string;
}
