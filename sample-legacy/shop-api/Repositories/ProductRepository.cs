using Dapper;
using Microsoft.Data.SqlClient;
using ShopApi.Models;

namespace ShopApi.Repositories;

public class ProductRepository
{
    private readonly string _connectionString;

    public ProductRepository(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("ShopDB")!;
    }

    public async Task<IEnumerable<Product>> GetAll()
    {
        using var conn = new SqlConnection(_connectionString);
        return await conn.QueryAsync<Product>("SELECT Id, Name, Price FROM Products");
    }
}
