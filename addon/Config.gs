function getConfig_() {
  var props = PropertiesService.getScriptProperties();
  var url = props.getProperty('BACKEND_URL');
  if (!url) {
    throw new Error(
      'BACKEND_URL is not set. open project settings > script properties and add ' +
      'BACKEND_URL (and optionally API_KEY).'
    );
  }
  return {
    backendUrl: url.replace(/\/+$/, ''),
    apiKey: props.getProperty('API_KEY') || ''
  };
}
