using ShopApi.Models;

namespace ShopApi.Services;

public interface ICustomerService
{
    Task<IEnumerable<OrderSummary>> GetOrders(int customerId);
}
