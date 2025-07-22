self.addEventListener('push', function(event) {
  let data = {};
  if (event.data) {
    data = event.data.json();
  }
  const title = data.title || 'Crypto Alert';
  const options = {
    body: data.body || '',
    icon: '/static/icon.png',
    badge: '/static/icon.png'
  };
  event.waitUntil(self.registration.showNotification(title, options));
}); 