import { Link, Navigate, Route, Routes } from 'react-router-dom'
import ProductList from './pages/ProductList'
import CustomerOrders from './pages/CustomerOrders'
import OrderDetails from './pages/OrderDetails'

export default function App() {
  return (
    <>
      <nav>
        <Link to="/products">Products</Link>
        <Link to="/customers/1/orders">Alice's orders</Link>
        <Link to="/customers/2/orders">Bob's orders</Link>
      </nav>
      <div className="container">
        <Routes>
          <Route path="/" element={<Navigate to="/products" replace />} />
          <Route path="/products" element={<ProductList />} />
          <Route path="/customers/:customerId/orders" element={<CustomerOrders />} />
          <Route path="/orders/:id" element={<OrderDetails />} />
        </Routes>
      </div>
    </>
  )
}
