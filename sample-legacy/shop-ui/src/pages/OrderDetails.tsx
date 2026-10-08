import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { isAxiosError } from 'axios'
import { client } from '../api/client'

interface OrderItem {
  productName: string
  quantity: number
  unitPrice: number
}

interface Order {
  orderId: number
  customerName: string
  status: string
  total: number
  items: OrderItem[]
}

export default function OrderDetails() {
  const { id } = useParams()
  const [order, setOrder] = useState<Order | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    setError(null)
    client
      .get(`/api/orders/${id}`)
      .then((res) => setOrder(res.data))
      .catch(() => setError('Failed to load order.'))
  }

  useEffect(load, [id])

  const cancel = () => {
    client
      .post(`/api/orders/${id}/cancel`)
      .then(() => load())
      .catch((err) => {
        const message = isAxiosError(err) ? err.response?.data?.error : undefined
        setError(message ?? 'Cancel failed.')
      })
  }

  return (
    <div>
      <h1>Order {id}</h1>
      {error && <p className="error">{error}</p>}
      {order && (
        <>
          <p>
            Customer: <strong>{order.customerName}</strong> &middot; Status:{' '}
            <strong>{order.status}</strong>
          </p>
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Qty</th>
                <th>Unit price</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item, index) => (
                <tr key={index}>
                  <td>{item.productName}</td>
                  <td>{item.quantity}</td>
                  <td>{item.unitPrice.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={2}>
                  <strong>Total</strong>
                </td>
                <td>
                  <strong>{order.total.toFixed(2)}</strong>
                </td>
              </tr>
            </tfoot>
          </table>
          <p style={{ marginTop: '1rem' }}>
            <button type="button" onClick={cancel}>
              Cancel order
            </button>
          </p>
        </>
      )}
      <p style={{ marginTop: '1rem' }}>
        <Link to="/products">&larr; Products</Link>
      </p>
    </div>
  )
}
