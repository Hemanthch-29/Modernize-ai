import { Routes } from '@angular/router';
import { ProductListComponent } from './pages/product-list/product-list';
import { CustomerOrdersComponent } from './pages/customer-orders/customer-orders';
import { OrderDetailsComponent } from './pages/order-details/order-details';

export const routes: Routes = [
  { path: '', redirectTo: 'products', pathMatch: 'full' },
  { path: 'products', component: ProductListComponent },
  { path: 'customers/:customerId/orders', component: CustomerOrdersComponent },
  { path: 'orders/:id', component: OrderDetailsComponent },
];
