using ShopApi.Models;
using ShopApi.Repositories;

namespace ShopApi.Services;

public class CustomerService : ICustomerService
{
    private readonly IOrderRepository _orderRepository;

    public CustomerService(IOrderRepository orderRepository)
    {
        _orderRepository = orderRepository;
    }

    public Task<IEnumerable<OrderSummary>> GetOrders(int customerId)
        => _orderRepository.GetByCustomer(customerId);
}
