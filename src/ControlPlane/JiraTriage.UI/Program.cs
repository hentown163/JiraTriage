using JiraTriage.Core.Services;
using JiraTriage.Worker.Workers;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddRazorPages();
builder.Services.AddHttpClient();
builder.Services.AddSingleton<IQueuePublisher, InMemoryQueuePublisher>();
builder.Services.AddSingleton<DecisionLogService>();
builder.Services.AddHostedService<TicketEnrichmentWorker>();

builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenAnyIP(5000);
});

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
}

app.UseStaticFiles();
app.UseRouting();
app.UseAuthorization();
app.MapRazorPages();

app.Run();
