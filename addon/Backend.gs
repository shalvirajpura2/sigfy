function requestDraft_(email) {
  var cfg = getConfig_();
  var headers = {
    'Bypass-Tunnel-Reminder': 'true'
  };
  if (cfg.apiKey) {
    headers['X-API-Key'] = cfg.apiKey;
  }

  var response = UrlFetchApp.fetch(cfg.backendUrl + '/draft', {
    method: 'post',
    contentType: 'application/json',
    headers: headers,
    payload: JSON.stringify({
      subject: email.subject,
      sender: email.sender,
      receiver: email.receiver || email.sender,
      body: email.body
    }),
    muteHttpExceptions: true
  });

  var code = response.getResponseCode();
  var text = response.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error('backend returned ' + code + ': ' + text.slice(0, 300));
  }
  return JSON.parse(text);
}
