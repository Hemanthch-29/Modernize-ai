using ShopApi.Repositories;
using ShopApi.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

// Controller -> Service -> Repository -> stored procedure
builder.Services.AddScoped<IOrderRepository, OrderRepository>();
builder.Services.AddScoped<ProductRepository>();
builder.Services.AddScoped<IOrderService, OrderService>();
builder.Services.AddScoped<ICustomerService, CustomerService>();

var app = builder.Build();

app.MapControllers();

app.Run();
