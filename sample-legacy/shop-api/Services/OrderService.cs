using Microsoft.Data.SqlClient;
using ShopApi.Models;
using ShopApi.Repositories;

namespace ShopApi.Services;

public class OrderService : IOrderService
{
    private readonly IOrderRepository _orderRepository;

    public OrderService(IOrderRepository orderRepository)
    {
        _orderRepository = orderRepository;
    }

    public Task<Order?> GetOrder(int id) => _orderRepository.GetById(id);

    public async Task<CancelResult> CancelOrder(int id)
    {
        var order = await _orderRepository.GetById(id);
        if (order is null)
            return new CancelResult(CancelStatus.NotFound);

        try
        {
            await _orderRepository.Cancel(id);
            return new CancelResult(CancelStatus.Ok);
        }
        catch (SqlException ex)
        {
            // Business-rule violations are raised via THROW in usp_CancelOrder.
            return new CancelResult(CancelStatus.Conflict, ex.Message);
        }
    }
}
