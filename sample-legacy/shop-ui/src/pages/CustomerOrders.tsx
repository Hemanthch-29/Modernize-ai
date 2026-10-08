import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { client } from '../api/client'

interface OrderSummary {
  orderId: number
  status: string
}

export default function CustomerOrders() {
  const { customerId } = useParams()
  const [orders, setOrders] = useState<OrderSummary[]>([])

  useEffect(() => {
    client
      .get(`/api/customers/${customerId}/orders`)
      .then((res) => setOrders(res.data))
  }, [customerId])

  return (
    <div>
      <h1>Orders for customer {customerId}</h1>
      <table>
        <thead>
          <tr>
            <th>Order</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.orderId}>
              <td>{o.orderId}</td>
              <td>{o.status}</td>
              <td>
                <Link to={`/orders/${o.orderId}`}>details</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
