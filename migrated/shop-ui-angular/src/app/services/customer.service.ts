import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { OrderSummary } from '../models/order.model';

@Injectable({ providedIn: 'root' })
export class CustomerService {
  private readonly http = inject(HttpClient);

  getOrders(customerId: string | number): Observable<OrderSummary[]> {
    return this.http.get<OrderSummary[]>(`/api/customers/${customerId}/orders`);
  }
}
