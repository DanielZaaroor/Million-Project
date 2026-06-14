# Non serious file about my journee understanding whatsapp.
> [!NOTE]
> - I don't actually have the will power to write everythin, maybe one day.
> - So im just going to copy what i already havve...

## Editing
### Encryption
Sometimes wuzapi figure the encryption itself, sometimes it does'nt.  
Read [code/utils.py](./code/utils.py) to see the absolute pigeon shit i pulled to figure this up.
### Edit field in the JSON event
| Value  | Constant  | Meaning
| -------|-----------|--------
|   ""   | EditAttributeEmpty | Normal message, no edit
|   "1"   | EditAttributeMessageEdit | Message was edited by sender
|   "2"   | EditAttributePinInChat | Message was pinned in chat
|   "3"   | EditAttributeAdminEdit | Admin edit (newsletters only)
|   "7"   | EditAttributeSenderRevoke | Deleted by sender (delete for everyone)
|   "8"   | EditAttributeAdminRevoke | Deleted by group admin

## Message Event Examples:
> [!WARNING]
> Maybe its not wise to put my private details on json events, so imma redact this first.
> use this [amazing site](https://json.site/) to format json!
### Regular Message
{"instanceName":"MyBot","jsonData":{"event":{"Info":{"Chat":"----@g.us","Sender":"----@lid","IsFromMe":true,"IsGroup":true,"AddressingMode":"lid","SenderAlt":"","RecipientAlt":"","BroadcastListOwner":"","BroadcastRecipients":null,"ID":"----","ServerID":0,"Type":"text","PushName":"—-","Timestamp":"2026-05-16T10:58:19","Category":"","Multicast":false,"MediaType":"","Edit":"","MsgBotInfo":{"EditType":"","EditTargetID":"","EditSenderTimestampMS":"0001-01-01T00:00:00Z"},"MsgMetaInfo":{"TargetID":"","TargetSender":"","TargetChat":"","DeprecatedLIDSession":null,"ThreadMessageID":"","ThreadMessageSenderJID":""},"VerifiedName":null,"DeviceSentMeta":null},"Message":{"conversation":"431316","messageContextInfo":{"messageSecret":"----="}},"IsEphemeral":false,"IsViewOnce":false,"IsViewOnceV2":false,"IsViewOnceV2Extension":false,"IsDocumentWithCaption":false,"IsLottieSticker":false,"IsBotInvoke":false,"IsEdit":false,"SourceWebMsg":null,"UnavailableRequestID":"","RetryCount":0,"NewsletterMeta":null,"RawMessage":{"conversation":"431316","messageContextInfo":{"messageSecret":"-----="}}},"type":"Message"},"userID":"-----"}
### Edited Encrypted Message
{"instanceName":"MyBot","jsonData":{"event":{"Info":{"Chat":"----@g.us","Sender":"----@lid","IsFromMe":true,"IsGroup":true,"AddressingMode":"lid","SenderAlt":"","RecipientAlt":"","BroadcastListOwner":"","BroadcastRecipients":null,"ID":"------","ServerID":0,"Type":"text","PushName":"---","Timestamp":"2026-05-16T10:58:36","Category":"","Multicast":false,"MediaType":"","Edit":"1","MsgBotInfo":{"EditType":"","EditTargetID":"","EditSenderTimestampMS":"0001-01-01T00:00:00Z"},"MsgMetaInfo":{"TargetID":"","TargetSender":"","TargetChat":"","DeprecatedLIDSession":null,"ThreadMessageID":"","ThreadMessageSenderJID":""},"VerifiedName":null,"DeviceSentMeta":null},"Message":{"secretEncryptedMessage":{"targetMessageKey":{"remoteJID":"----@g.us","fromMe":true,"ID":"----"},"encPayload":"----","encIV":"----","secretEncType":2}},"IsEphemeral":false,"IsViewOnce":false,"IsViewOnceV2":false,"IsViewOnceV2Extension":false,"IsDocumentWithCaption":false,"IsLottieSticker":false,"IsBotInvoke":false,"IsEdit":false,"SourceWebMsg":null,"UnavailableRequestID":"","RetryCount":0,"NewsletterMeta":null,"RawMessage":{"secretEncryptedMessage":{"targetMessageKey":{"remoteJID":"----@g.us","fromMe":true,"ID":"----"},"encPayload":"----","encIV":"----","secretEncType":2}}},"type":"Message"},"userID":"----”}
