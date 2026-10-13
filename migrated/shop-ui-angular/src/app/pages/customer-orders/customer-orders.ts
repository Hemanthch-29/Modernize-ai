import { Component, inject, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { switchMap } from 'rxjs';
import { CustomerService } from '../../services/customer.service';
import { OrderSummary } from '../../models/order.model';

@Component({
  selector: 'app-customer-orders',
  imports: [RouterLink],
  templateUrl: './customer-orders.html',
})
export class CustomerOrdersComponent {
  private readonly customerService = inject(CustomerService);

  // Bound from the route param (:customerId) via withComponentInputBinding().
  readonly customerId = input.required<string>();

  readonly orders = toSignal(
    toObservable(this.customerId).pipe(
      switchMap((id) => this.customerService.getOrders(id)),
    ),
    { initialValue: [] as OrderSummary[] },
  );
}
