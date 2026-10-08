using ShopApi.Models;

namespace ShopApi.Repositories;

public interface IOrderRepository
{
    Task<Order?> GetById(int id);
    Task<IEnumerable<OrderSummary>> GetByCustomer(int customerId);
    Task Cancel(int id);
}
