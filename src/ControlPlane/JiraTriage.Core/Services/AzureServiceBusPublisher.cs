using System.Text;
using System.Text.Json;
using Azure.Identity;
using Azure.Messaging.ServiceBus;

namespace JiraTriage.Core.Services;

public class AzureServiceBusPublisher : IAsyncDisposable
{
    private readonly ServiceBusClient _client;
    private readonly Dictionary<string, ServiceBusSender> _senders;
    private readonly SemaphoreSlim _lock = new(1, 1);
    private bool _disposed;

    public AzureServiceBusPublisher(string serviceBusNamespace, bool useLocalEmulator = false)
    {
        if (useLocalEmulator)
        {
            var connectionString = Environment.GetEnvironmentVariable("SERVICEBUS_CONNECTION_STRING") 
                ?? throw new InvalidOperationException("SERVICEBUS_CONNECTION_STRING not set for local emulator");
            _client = new ServiceBusClient(connectionString);
        }
        else
        {
            var credential = new DefaultAzureCredential();
            _client = new ServiceBusClient(serviceBusNamespace, credential);
        }
        
        _senders = new Dictionary<string, ServiceBusSender>();
        Console.WriteLine($"[ServiceBus] Initialized publisher for namespace: {serviceBusNamespace}");
    }

    public static AzureServiceBusPublisher CreateFromEnvironment()
    {
        var useLocal = Environment.GetEnvironmentVariable("USE_LOCAL_SERVICEBUS")?.ToLower() == "true";
        var serviceBusNamespace = Environment.GetEnvironmentVariable("SERVICEBUS_NAMESPACE") 
            ?? "jiratriage.servicebus.windows.net";
        
        return new AzureServiceBusPublisher(serviceBusNamespace, useLocal);
    }

    private async Task<ServiceBusSender> GetOrCreateSenderAsync(string queueName)
    {
        if (_senders.TryGetValue(queueName, out var existingSender))
        {
            return existingSender;
        }

        await _lock.WaitAsync();
        try
        {
            if (_senders.TryGetValue(queueName, out existingSender))
            {
                return existingSender;
            }

            var sender = _client.CreateSender(queueName);
            _senders[queueName] = sender;
            Console.WriteLine($"[ServiceBus] Created sender for queue: {queueName}");
            return sender;
        }
        finally
        {
            _lock.Release();
        }
    }

    public async Task PublishAsync<T>(string queueName, T message, Dictionary<string, object>? properties = null) where T : class
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(AzureServiceBusPublisher));
        }

        try
        {
            var sender = await GetOrCreateSenderAsync(queueName);
            
            var jsonMessage = JsonSerializer.Serialize(message);
            var serviceBusMessage = new ServiceBusMessage(Encoding.UTF8.GetBytes(jsonMessage))
            {
                ContentType = "application/json",
                MessageId = Guid.NewGuid().ToString()
            };

            if (properties != null)
            {
                foreach (var prop in properties)
                {
                    serviceBusMessage.ApplicationProperties[prop.Key] = prop.Value;
                }
            }

            await sender.SendMessageAsync(serviceBusMessage);
            
            Console.WriteLine($"[ServiceBus] Published to {queueName}: {typeof(T).Name} (MessageId: {serviceBusMessage.MessageId})");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ServiceBus] Error publishing to {queueName}: {ex.Message}");
            throw;
        }
    }

    public async Task PublishBatchAsync<T>(string queueName, IEnumerable<T> messages) where T : class
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(AzureServiceBusPublisher));
        }

        try
        {
            var sender = await GetOrCreateSenderAsync(queueName);
            var messageList = messages.ToList();
            var totalMessages = messageList.Count;
            var sentCount = 0;
            var batchNumber = 1;

            while (sentCount < totalMessages)
            {
                using var messageBatch = await sender.CreateMessageBatchAsync();
                var batchCount = 0;

                for (int i = sentCount; i < totalMessages; i++)
                {
                    var jsonMessage = JsonSerializer.Serialize(messageList[i]);
                    var serviceBusMessage = new ServiceBusMessage(Encoding.UTF8.GetBytes(jsonMessage))
                    {
                        ContentType = "application/json",
                        MessageId = Guid.NewGuid().ToString()
                    };

                    if (!messageBatch.TryAddMessage(serviceBusMessage))
                    {
                        break;
                    }

                    batchCount++;
                    sentCount++;
                }

                if (batchCount > 0)
                {
                    await sender.SendMessagesAsync(messageBatch);
                    Console.WriteLine($"[ServiceBus] Sent batch #{batchNumber} with {batchCount} messages to {queueName} (Total: {sentCount}/{totalMessages})");
                    batchNumber++;
                }
                else
                {
                    throw new InvalidOperationException($"Message at index {sentCount} is too large to fit in a single batch");
                }
            }

            Console.WriteLine($"[ServiceBus] Successfully published all {totalMessages} messages to {queueName} in {batchNumber - 1} batch(es)");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ServiceBus] Error publishing batch to {queueName}: {ex.Message}");
            throw;
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;

        await _lock.WaitAsync();
        try
        {
            foreach (var sender in _senders.Values)
            {
                await sender.DisposeAsync();
            }
            _senders.Clear();
        }
        finally
        {
            _lock.Release();
        }

        await _client.DisposeAsync();
        _lock.Dispose();
        
        Console.WriteLine("[ServiceBus] Publisher disposed");
    }
}
