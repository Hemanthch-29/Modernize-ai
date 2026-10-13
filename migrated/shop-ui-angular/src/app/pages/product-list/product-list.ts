import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ProductService } from '../../services/product.service';
import { Product } from '../../models/product.model';

@Component({
  selector: 'app-product-list',
  templateUrl: './product-list.html',
})
export class ProductListComponent {
  private readonly productService = inject(ProductService);

  readonly products = toSignal(this.productService.getAll(), {
    initialValue: [] as Product[],
  });
}
