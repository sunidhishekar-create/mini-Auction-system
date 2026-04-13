import socket
import threading

SERVER = "127.0.0.1"
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER, PORT))


def receive_messages():
    while True:
        try:
            message = client.recv(1024).decode()
            print(message)
        except:
            break


receive_thread = threading.Thread(target=receive_messages)
receive_thread.daemon = True
receive_thread.start()

while True:
    message = input()

    if message.lower() == "exit":
        client.send("exit".encode())
        break

    client.send(message.encode())

client.close()
print("Disconnected from auction server")