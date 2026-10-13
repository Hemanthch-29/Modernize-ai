import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { Order } from '../models/order.model';

// Relative /api URLs go through the Angular dev proxy to the FastAPI backend (proxy.conf.json).
@Injectable({ providedIn: 'root' })
export class OrderService {
  private readonly http = inject(HttpClient);

  getOrder(id: string | number): Observable<Order> {
    return this.http.get<Order>(`/api/orders/${id}`);
  }

  cancelOrder(id: string | number): Observable<void> {
    return this.http.post<void>(`/api/orders/${id}/cancel`, {});
  }
}
