var BODY_LIMIT = 6000;

function onGmailMessageOpen(e) {
  try {
    var email = readCurrentEmail_(e);
    var result = requestDraft_(email);
    return buildDraftCard_(email, result, e);
  } catch (err) {
    return buildErrorCard_(err);
  }
}

function readCurrentEmail_(e) {
  var accessToken = e.gmail.accessToken;
  var messageId = e.gmail.messageId;
  GmailApp.setCurrentMessageAccessToken(accessToken);

  var message = GmailApp.getMessageById(messageId);
  var body = message.getPlainBody() || '';
  return {
    messageId: messageId,
    accessToken: accessToken,
    subject: message.getSubject() || '',
    sender: message.getFrom() || '',
    body: body.slice(0, BODY_LIMIT)
  };
}

function regenerate(e) {
  var card;
  try {
    var email = readCurrentEmail_(e);
    card = buildDraftCard_(email, requestDraft_(email), e);
  } catch (err) {
    card = buildErrorCard_(err);
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(card))
    .build();
}

function insertReply(e) {
  var params = e.parameters || {};
  var draft = (e.formInput && e.formInput.draft) || '';
  if (!draft.trim()) {
    return notify_('nothing to insert — the draft is empty.');
  }
  try {
    var token = (e.gmail && e.gmail.accessToken) || params.accessToken;
    GmailApp.setCurrentMessageAccessToken(token);
    GmailApp.getMessageById(params.messageId).createDraftReply(draft);
    return notify_('reply draft created — open the thread in gmail to review and send.');
  } catch (err) {
    return notify_('could not create the reply draft: ' + err.message);
  }
}

function notify_(text) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(text))
    .build();
}

function processInboxInBackground() {
  var query = 'is:unread label:inbox "FSA" OR "HCSA" OR "spending account" OR "reimbursement" OR "deductible" OR "copay" OR "coinsurance" OR "out-of-pocket" OR "braces" OR "orthodontic" OR "orthodontist" OR "dental" OR "dentist" OR "medical" OR "doctor" OR "specialist" OR "travel" OR "lodging" OR "hotel" OR "hospital" OR "critical illness" OR "indemnity" OR "vision" OR "eye" OR "optometrist" OR "glasses" OR "contacts" OR "long-term care" OR "LTC" OR "enrollment" OR "benefits" -label:"Benefits Assistant/Drafted"';
  var threads = GmailApp.search(query, 0, 10);
  var userProperties = PropertiesService.getUserProperties();
  
  var processedCount = 0;
  for (var i = 0; i < threads.length; i++) {
    if (processedCount >= 3) break;
    
    var thread = threads[i];
    var threadId = thread.getId();
    
    if (userProperties.getProperty("proc_" + threadId)) {
      continue;
    }
    
    var messages = thread.getMessages();
    var lastMessage = messages[messages.length - 1];
    
    if (lastMessage.getFrom().indexOf(Session.getActiveUser().getEmail()) !== -1) {
      userProperties.setProperty("proc_" + threadId, "1");
      continue;
    }
    
    try {
      var emailContext = {
        subject: lastMessage.getSubject(),
        sender: lastMessage.getFrom(),
        body: lastMessage.getPlainBody().slice(0, BODY_LIMIT)
      };
      
      var result = requestDraft_(emailContext);
      
      if (result && result.draft && result.found) {
        lastMessage.createDraftReply(result.draft);
        applyLabelToThread_(thread, "Benefits Assistant/Drafted");
      }
      
      userProperties.setProperty("proc_" + threadId, "1");
      processedCount++;
      
      Utilities.sleep(3000);
      
    } catch (e) {
      Logger.log("Error background drafting thread " + thread.getId() + ": " + e.toString());
    }
  }
}

function applyLabelToThread_(thread, labelName) {
  var label = GmailApp.getUserLabelByName(labelName);
  if (!label) {
    label = GmailApp.createLabel(labelName);
  }
  thread.addLabel(label);
}
