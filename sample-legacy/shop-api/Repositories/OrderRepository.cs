using System.Data;
using Dapper;
using Microsoft.Data.SqlClient;
using ShopApi.Models;

namespace ShopApi.Repositories;

public class OrderRepository : IOrderRepository
{
    private readonly string _connectionString;

    public OrderRepository(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("ShopDB")!;
    }

    public async Task<Order?> GetById(int id)
    {
        using var conn = new SqlConnection(_connectionString);
        using var multi = await conn.QueryMultipleAsync(
            "usp_GetOrderById",
            new { OrderId = id },
            commandType: CommandType.StoredProcedure);

        var order = await multi.ReadFirstOrDefaultAsync<Order>();
        if (order is null)
            return null;

        order.Items = (await multi.ReadAsync<OrderItem>()).ToList();
        return order;
    }

    public async Task<IEnumerable<OrderSummary>> GetByCustomer(int customerId)
    {
        using var conn = new SqlConnection(_connectionString);
        return await conn.QueryAsync<OrderSummary>(
            "usp_GetOrdersByCustomer",
            new { CustomerId = customerId },
            commandType: CommandType.StoredProcedure);
    }

    public async Task Cancel(int id)
    {
        using var conn = new SqlConnection(_connectionString);
        await conn.ExecuteAsync(
            "usp_CancelOrder",
            new { OrderId = id },
            commandType: CommandType.StoredProcedure);
    }
}
