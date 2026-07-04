function buildDraftCard_(email, result, e) {
  var builder = CardService.newCardBuilder();
  builder.setHeader(
    CardService.newCardHeader()
      .setTitle('sigfy benefits assistant')
      .setSubtitle(email.subject || '(no subject)')
  );

  builder.addSection(statusSection_(result));
  builder.addSection(draftSection_(result));
  builder.addSection(sourcesSection_(result));
  if (result.notes) {
    builder.addSection(
      CardService.newCardSection()
        .setHeader('notes')
        .addWidget(CardService.newTextParagraph().setText(escape_(result.notes)))
    );
  }
  builder.addSection(actionsSection_(email));
  return builder.build();
}

function statusSection_(result) {
  var section = CardService.newCardSection();
  if (!result.found) {
    section.addWidget(
      CardService.newDecoratedText()
        .setText('<b>no clear answer in the plan documents</b>')
        .setBottomLabel('review carefully — this draft asks to confirm rather than guessing')
        .setWrapText(true)
        .setStartIcon(CardService.newIconImage().setIcon(CardService.Icon.DESCRIPTION))
    );
  } else {
    section.addWidget(
      CardService.newDecoratedText()
        .setText('<b>grounded draft ready</b>')
        .setBottomLabel('confidence: ' + (result.confidence || 'medium'))
        .setStartIcon(CardService.newIconImage().setIcon(CardService.Icon.STAR))
    );
  }
  return section;
}

function draftSection_(result) {
  return CardService.newCardSection()
    .setHeader('drafted reply — edit before inserting')
    .addWidget(
      CardService.newTextInput()
        .setFieldName('draft')
        .setMultiline(true)
        .setValue(result.draft || '')
    );
}

function sourcesSection_(result) {
  var section = CardService.newCardSection().setHeader('sources');
  var citations = result.citations || [];
  if (!citations.length) {
    section.addWidget(
      CardService.newTextParagraph().setText('no supporting section was cited.')
    );
    return section;
  }
  citations.forEach(function (c) {
    var meta = [];
    if (c.section) meta.push(c.section);
    if (c.page) meta.push('page ' + c.page);
    var widget = CardService.newDecoratedText()
      .setTopLabel(c.document)
      .setText(meta.join(' · ') || 'section n/a')
      .setWrapText(true)
      .setStartIcon(CardService.newIconImage().setIcon(CardService.Icon.BOOKMARK));
    if (c.quote) {
      widget.setBottomLabel('"' + c.quote + '"');
    }
    section.addWidget(widget);
  });
  return section;
}

function actionsSection_(email) {
  var params = { messageId: email.messageId };

  var insert = CardService.newTextButton()
    .setText('insert as reply draft')
    .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
    .setOnClickAction(
      CardService.newAction().setFunctionName('insertReply').setParameters(params)
    );

  var regen = CardService.newTextButton()
    .setText('regenerate')
    .setOnClickAction(CardService.newAction().setFunctionName('regenerate'));

  return CardService.newCardSection().addWidget(
    CardService.newButtonSet().addButton(insert).addButton(regen)
  );
}

function buildErrorCard_(err) {
  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('benefits reply assistant'))
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setText('<b>could not draft a reply</b>')
            .setBottomLabel(escape_(err.message || String(err)))
            .setWrapText(true)
            .setStartIcon(CardService.newIconImage().setIcon(CardService.Icon.DESCRIPTION))
        )
        .addWidget(
          CardService.newTextParagraph().setText(
            'check that BACKEND_URL (and API_KEY) are set in script properties and ' +
            'that the backend is reachable.'
          )
        )
    )
    .build();
}

function escape_(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
