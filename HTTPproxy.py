# Place your imports here
'''
Zachary Gundersen wrote this code
'''
import signal
import sys
import re
import threading
from datetime import datetime

from optparse import OptionParser
from urllib.parse import urlparse

# Signal handler for pressing ctrl-c

from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

cache = False
blocker = False
blocklist = []
cacheDictionary = {}
currentfiles = 3


def ctrl_c_pressed(signal, frame):
    sys.exit(0)


'''
This method is my main method it handles interacting with a single connection 
'''


def runSocket(connectionSocket, address1):
    # these are my global methods that help set up my cache and blocklist
    global blocker
    global cache
    global blocklist
    global cacheDictionary
    global currentfiles
    sentence = ""
    while re.search("\r\n\r\n", sentence) is None:
        # we take every piece of the data that is being sent if at anypoint
        # the connection is interrupted before we get the \r\n\r\n
        # then we just return because we know the client shut down the connection
        newSentence = connectionSocket.recv(1024).decode()
        if len(newSentence) == 0:
            return
        # if len(newSentence) == 0:
        #    continue
        sentence += newSentence
        # some sort of check if the socket is closed then we return an error
    sentences = sentence.split("\r\n")
    first = sentences[0]
    sentences.pop(0)
    firstBlock = first.split(" ", 3)
    protocol = firstBlock[1].split("://")
    notimplemented = ["HEAD", "POST"]

    # these if statements make sure the get line is formatted correctly
    if len(firstBlock) != 3:
        connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
        connectionSocket.close()
        return
    elif firstBlock[0] in notimplemented:
        # return not executed
        # close connection
        connectionSocket.send("HTTP/1.0 501 Not Implemented".encode())
        connectionSocket.close()
        return
    elif firstBlock[0] != "GET":
        print(firstBlock[0])
        connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
        connectionSocket.close()
        return
    elif len(protocol) != 2:
        connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
        connectionSocket.close()
        return
    elif len(protocol[1].split("/")) < 2:
        connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
        connectionSocket.close()
        return
    elif len(protocol[1].split()) > 2:
        connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
        connectionSocket.close()
        return
    elif firstBlock[2] != "HTTP/1.0":
        connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
        connectionSocket.close()
        return
    else:
        url = urlparse(firstBlock[1])
        first = firstBlock[0] + " " + url.path + " " + firstBlock[2]

    # this checks if the url path is one of our special commands, if it is it applys the command and
    # returns the 200 ok message and closes the socket
    if url.path == "/proxy/cache/enable":
        cache = True
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return
    elif url.path == "/proxy/cache/disable":
        cache = False
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return
    elif url.path == "/proxy/cache/flush":
        # might need some file maintenance
        cacheDictionary.clear()
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return
    elif url.path == "/proxy/blocklist/enable":
        blocker = True
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return
    elif url.path == "/proxy/blocklist/disable":
        blocker = False
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return
    elif url.path == "/proxy/blocklist/flush":
        blocklist.clear()
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return
    elif url.path.startswith("/proxy/blocklist/add/"):
        urlHalves = url.path.split("/proxy/blocklist/add/", 1)
        blocklist.append(urlHalves[1])
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return
    elif url.path.startswith("/proxy/blocklist/remove/"):
        urlHalves = url.path.split("/proxy/blocklist/remove/", 1)
        if urlHalves[1] in blocklist:
            blocklist.remove(urlHalves[1])
        connectionSocket.send("HTTP/1.0 200 OK".encode())
        connectionSocket.close()
        return

    if blocker:
        for x in blocklist:
            # we check if anything in the blocklist is a substring of url.netloc
            # netloc includes both the hostname and the port
            if x in url.netloc:
                connectionSocket.send("HTTP/1.0 403 Forbidden".encode())
                connectionSocket.close()
                return

    # this for loop checks the headers to make sure they are in the correct state
    count = -1
    cont = False
    sentences.pop()
    sentences.pop()
    newSentences = ""
    for x in sentences:

        xParts = x.split(": ")

        if len(xParts) != 2:
            # return an error malformed expression
            connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
            connectionSocket.close()
            cont = True
            break
        if len(xParts[0].strip()) != len(xParts[0]):
            connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
            connectionSocket.close()
            cont = True
            break
        if len(xParts[1].strip()) != len(xParts[1]):
            connectionSocket.send("HTTP/1.0 400 Bad Request".encode())
            connectionSocket.close()
            cont = True
            break
        if xParts[0] == "Connection":
            newSentences += "Connection: close\r\n"
            # Send the message to the desired server
        else:
            newSentences += x + "\r\n"
    if cont:
        return

        # this section makes sure that the url and the message to the server is in the right format
    serverName = url.hostname
    if url.port is None:
        serverPort = 80
    else:
        serverPort = url.port
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.connect((serverName, serverPort))

    # this section checks if the cache is enabled, if it is uses the cache to
    # determine the appropriate action to take
    if cache:
        # if url is in the cacheDictionary it deals with it if not it continues on to the regular
        # get request
        if firstBlock[1] in cacheDictionary:
            # think about this one some more
            thedate = cacheDictionary[firstBlock[1]][1]
            file = cacheDictionary[firstBlock[1]][0]
            first = first + "\r\n" + "Host: " + url.hostname + "\r\n" + "If-Modified-Since: " + thedate + "\r\n\r\n"
            clientSocket.send(first.encode())
            sentenceFromServer = b''
            while True:
                thisSentence = clientSocket.recv(1024)
                if len(thisSentence) == 0:
                    break
                sentenceFromServer += thisSentence
            Thesentence = sentenceFromServer.split(b"\r\n\r\n", 1)[0]
            TheSentences = Thesentence.decode().split("\r\n")[0]
            # checks if the returned data says not modified
            if "304 Not Modified" in TheSentences:
                thefile = open(file, "rb")
                cachedSentence = thefile.read()

                connectionSocket.send(cachedSentence)
                thefile.close()
                connectionSocket.close()
            else:
                # makes a  new file and replaces the old file with the new information
                thefile = open(f"{currentfiles}", "wb")

                thefile.write(sentenceFromServer)
                cacheDictionary[firstBlock[1]] = (f"{currentfiles}", thedate)
                connectionSocket.send(sentenceFromServer)
                thefile.close()
                connectionSocket.close()
                currentfiles += 1
            return
    first = first + "\r\n" + "Host: " + url.hostname + "\r\n" "Connection: close" + "\r\n" + newSentences + "\r\n"
    clientSocket.send(first.encode())
    sentenceFromServer = b''

    while True:
        thisSentence = clientSocket.recv(1024)
        if len(thisSentence) == 0:
            break
        sentenceFromServer += thisSentence
        # Wait for a response from the server

        # this if the cache is activated takes the message apart and find the Last Modified date and stores the
        # appropriate data into the cache and then sends on the response
    if cache:
        Thesentence = sentenceFromServer.split(b"\r\n\r\n", 1)[0]
        TheSentences = Thesentence.decode().split("\r\n")
        date = ""
        date2 = ""
        for x in TheSentences:
            xParts = x.split(": ")
            if xParts[0] == "Last-Modified":
                date = xParts[1]
            if xParts[0] == "Date":
                date2 = xParts[1]
        theDate = ""
        if date != "":
            theDate = date
        else:
            theDate = date2
        file = open(f"{currentfiles}", "wb")

        file.write(sentenceFromServer)
        file.close()
        cacheDictionary[firstBlock[1]] = (f"{currentfiles}", theDate)
        currentfiles += 1
        # Send the response received back to the original client
    clientSocket.close()
    connectionSocket.send(sentenceFromServer)
    # close connections.
    connectionSocket.close()


# TODO: Put function definitions here


# Start of program execution
# Parse out the command line server address and port number to listen to
parser = OptionParser()
parser.add_option('-p', type='int', dest='serverPort')
parser.add_option('-a', type='string', dest='serverAddress')
(options, args) = parser.parse_args()

port = options.serverPort
address = options.serverAddress
if address is None:
    address = 'localhost'
if port is None:
    port = 2100

# Set up signal handling (ctrl-c)
signal.signal(signal.SIGINT, ctrl_c_pressed)

# TODO: Set up sockets to receive requests
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
serverSocket.bind((address, port))
serverSocket.listen()
print("The server is ready")
while True:
    # TODO: accept and handle connections
    # accept the incoming client
    connectSocket, address = serverSocket.accept()

    # starts a thread everytime we have a new connection and performs the
    # necessary actions
    sock = threading.Thread(target=runSocket, args=(connectSocket, address))
    sock.start()
