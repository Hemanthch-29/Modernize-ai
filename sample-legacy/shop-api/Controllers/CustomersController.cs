using Microsoft.AspNetCore.Mvc;
using ShopApi.Services;

namespace ShopApi.Controllers;

[ApiController]
[Route("api/customers")]
public class CustomersController : ControllerBase
{
    private readonly ICustomerService _customerService;

    public CustomersController(ICustomerService customerService)
    {
        _customerService = customerService;
    }

    [HttpGet("{id:int}/orders")]
    public async Task<IActionResult> GetOrders(int id)
    {
        var orders = await _customerService.GetOrders(id);
        return Ok(orders);
    }
}
