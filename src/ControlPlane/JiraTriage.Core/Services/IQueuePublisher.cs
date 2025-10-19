namespace JiraTriage.Core.Services;

public interface IQueuePublisher
{
    Task PublishAsync<T>(string queueName, T message) where T : class;
}
