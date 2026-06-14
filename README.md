# Million-Project
Goal - Improving the counting flow of the group by checking for errors and missing numnbers.

> [!IMPORTANT]
> - For full Project setup details, read [SETUP.md](./SETUP.md).
> - To dive straight into the code, checkout the [code dir](./code)
> - For message examples and whatsapp quirks, go to [Whats_up_whatsapp.md](./Whats_up_whatsapp.md)

## 1. The Problem - automating the check flow of the WhatsApp group “counting to million”
- Group Rules:
  - Every message must contain a valid number! (previous_num+1) the rest of the message can be anything you want. The number can be written at any place in the message.
  - The same person can’t write more than one number in a row.
  - Delete duplicate numbers - there should only be one copy of each number. Admins will delete incorrect messages.
  - No commas in numbers. No Stickers/gifs allowed.
  - Mistakes can be fixed, as long as the counting flow stays intact
- The group is already running, with a current number around 410,000. Admins manually check each number, sometimes mistakes can be found hours later.
- Ideally, mistakes should be found in the 15 minutes window when users can still edit the incorrect numbers. If not, the progress after the mistake will be lost.

## 2. The Solution - building a Headless Automation
- The journee of a message:
  1. Filters - sent to the target group, not a sticker, has text, following rules.
  2. If it's valid (different sender, prev+1) - register to DB.
  3. Else, start the mistake window - wait 1 minutes for it to be edited. Then send an alert. All messages sent in the mistake window will be quickly checked for the absent number, then saved on a buffer and checked after the fix.
  4. If the mistake was fixed by editing, check the buffer. If by someone else, the buffer messages will be deleted, we don't need those messages anymore.
  5. Immediate alerts will be sent only for non-mistake events, like stickers or double messages from the same sender.
  > If the mistake was fixed before the alert fired, it will not fire.
- Architecture:
  - We will use Wuzapi for WhatsApp integration, RabbitMQ for message queuing, and a Python app for the actual logic. Previous numbers will be saved on SQLite DB.
  - Wuzapi - acts as a connected device, like Whatsapp web. Uses the Noise Protocol to receive all events related to the whatsapp account.
  - Those services will run as docker containers on an Ubuntu VM, managed by Docker-Compose
  - The code repository sits on Github, and using Github Actions we will deploy it to the VM and reload the services.
  - Diagram below:
  ![drawio diagram, also present in the repo.](https://drive.google.com/file/d/15v_vk_C5sg3od7v4OIKGHKp0227iYOyE/view?usp=drive_link)

## 3. Progress
1. Phase 1 - preparing the working environemt environment, described on [SETUP.md](./SETUP.md).
  > DoD -  
  > all 3 services are running - basic python code can read and print messages from RabbitMQ.  
  > Wuzapi connection is able to send messages back to whatsapp.
2. Phase 2 - logic engine V1
  - One main.py script, with functions dedicated only to the million group.
  - Later Refactored to handle edited messages.
  - CICD added with Github actions.
3. Phase 3 - logic engine V2:
  - Split the app into multiple files. main.py now initializes queue and route messages based on groups to specific scripts.
  - Admin actions added for immediate number override directly from phone, and to get current bot status.
