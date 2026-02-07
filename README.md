# Million-Project
Improving the counting flow of the group by checking for errors and missing numnbers.

## 1. Prequisites
Working environment for the services, I used an always-free Oracle Ampre Ubuntu VM.
I created a network and subnet before, than the VM.
It will probably only be available with an PAYGO account, but if configured right should stay free of cost.

With the new VM you can go to root and clone the repo , or create the files manually.
```
sudo mkdir /million-project /million-project/code /million-project/wuzapi-data
cd /million-project && touch .env docker-compose.yml code/Dockerfile code/main.py
```
> For later actually create this in git then do git clone instead, maybe from base branch to start with.
## 2. Installations
### docker
```
sudo apt update && sudo apt upgrade -y
sudo apt install ca-certificates curl gnupg lsb-release -y
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
```
**verify with:    docker run hello-world**
> To run docker commands without root, run this command then logout:     **sudo usermod -aG docker ${USER}**

Now create the containers (you should have cloned the repo already)
```
docker-compose up -d --build
docker-compose logs -f wuzapi | less 
```
last one is to view the logs.

### WuzAPI:
First, create a user:
```
curl -X POST http://localhost:8080/admin/users \
  -H "Authorization: my_secure_token_123" \
  -H "Content-Type: application/json" \
  -d '{"name": "MyBot", "token": "MyUserToken123"}'
```
Than create a session connection:
```
curl -X POST http://localhost:8080/session/connect \
  -H "Token: MyUserToken123" \
  -H "Content-Type: application/json" \
  -d '{"Subscribe":["Message","ReadReceipt"]}'

curl -s -H "Token: MyUserToken123" http://localhost:8080/session/qr
```
Now this will output a base64 image QR, you can eiter decode it from [This Site](https://base64.guru/converter/decode/image), or view the logs with the command from before.
