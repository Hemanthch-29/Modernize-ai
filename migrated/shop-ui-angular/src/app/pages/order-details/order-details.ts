import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { OrderService } from '../../services/order.service';
import { Order } from '../../models/order.model';

@Component({
  selector: 'app-order-details',
  imports: [RouterLink],
  templateUrl: './order-details.html',
})
export class OrderDetailsComponent {
  private readonly orderService = inject(OrderService);

  // Bound from the route param (:id) via withComponentInputBinding().
  readonly id = input.required<string>();
  readonly order = signal<Order | null>(null);
  readonly error = signal<string | null>(null);

  constructor() {
    effect(() => this.load(this.id()));
  }

  private load(id: string): void {
    this.error.set(null);
    this.orderService.getOrder(id).subscribe({
      next: (order) => this.order.set(order),
      error: () => this.error.set('Failed to load order.'),
    });
  }

  cancel(): void {
    this.orderService.cancelOrder(this.id()).subscribe({
      next: () => this.load(this.id()),
      error: (err: HttpErrorResponse) => {
        // The backend returns 409 { "error": "<message>" } for the shipped-order rule.
        const message = err.error?.error as string | undefined;
        this.error.set(message ?? 'Cancel failed.');
      },
    });
  }
}
