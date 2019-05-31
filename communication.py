# -*- coding: utf-8 -*-
"""
Created on Wed May 29 08:08:28 2019

@author: jirka
"""
import FreeCAD
from PySide2.QtCore import QThread, QByteArray, QDataStream, QIODevice
from PySide2.QtNetwork import QTcpServer, QTcpSocket, QAbstractSocket, QHostAddress

SIZEOF_UINT16 = 2
PORT = 31313
INVALID_ADDRESS = 1
PORT_OCCUPIED = 2
WAIT_TIME_MS = 30000

class CommandThread(QThread):

	def __init__(self, socketDescriptor, parent):
		super(CommandThread, self).__init__(parent)
		self.socketDescriptor = socketDescriptor
		self.blockSize = 0


	def run(self):
		tcpSocket = QTcpSocket()
		if not tcpSocket.setSocketDescriptor(self.socketDescriptor):
			self.error.emit(tcpSocket.error())
			return

		if not tcpSocket.waitForReadyRead(msecs=WAIT_TIME_MS):
			FreeCAD.Console.PrintError("No request send.\n")
			return

		instr = QDataStream(tcpSocket)
		instr.setVersion(QDataStream.Qt_4_0)

		if self.blockSize == 0:
			if tcpSocket.bytesAvailable() < 2:
				return
			self.blockSize = instr.readUInt16()

		if tcpSocket.bytesAvailable() < self.blockSize:
			return

		instr = instr.readString()
		FreeCAD.Console.PrintLog("Server received> " + str(instr) + "\n")
		
		try:
			exec(str(instr))
		except Exception as e :
			FreeCAD.Console.PrintError("Executing external command failed:" +\
									   str(e) + "\n")
			message = "Command failed - " + str(e)
		else:
			FreeCAD.Console.PrintLog("Executing external command succeded!\n")
			message = "Command executed succesfully"
		
		FreeCAD.Console.PrintLog("Server sending> " + message + " \n")
		block = QByteArray()
		outstr = QDataStream(block, QIODevice.WriteOnly)
		outstr.setVersion(QDataStream.Qt_4_0)
		outstr.writeUInt16(0)
		outstr.writeQString(message)
		outstr.device().seek(0)
		outstr.writeUInt16(block.size() - 2)
	
		tcpSocket.write(block)
		tcpSocket.disconnectFromHost()
		tcpSocket.waitForDisconnected()
		

class Srv(QTcpServer):
	def __init__(self, parent=None):
		super(Srv, self).__init__(parent)

	def incomingConnection(self, socketDescriptor):
		thread = CommandThread(socketDescriptor, self)
		thread.finished.connect(thread.deleteLater)
		thread.start()
		
	def close(self):
		super(Srv, self).close()
		FreeCAD.Console.PrintLog("Server closed.\n")


def check_ip_valid(ip):
	if ip.upper() == "LOCALHOST":
		return True
	numbers = ip.split(".")
	if len(numbers) == 4:
		if all([(0 <= int(num) <=255) for num in numbers]):
			return  True
	return False

def startServer(addr, port):
	""" addr = IPv4 address string or localhost"""
	FreeCAD.Console.PrintMessage ( str(addr) + "\n")

	if not check_ip_valid(addr):
		return INVALID_ADDRESS

	if addr.upper() == "LOCALHOST":
		addr = QHostAddress(QHostAddress.LocalHost)
	else:
		addr = QHostAddress(addr)
		
	server = Srv()
	if not server.listen(addr, port): 
		FreeCAD.Console.PrintLog( "Unable to start the server: %s.\n" % server.errorString())
		return PORT_OCCUPIED
	else:
		FreeCAD.Console.PrintLog("The server is running on port %d.\n" % server.serverPort())
		return server

class Client:
	
	def __init__(self, HOST, PORT):
		self.host = HOST
		self.port = PORT
		self.tcpSocket = QTcpSocket()
		self.blockSize = 0

		self.tcpSocket.connectToHost(self.host, self.port, QIODevice.ReadWrite)
		if not self.tcpSocket.waitForConnected(msecs=WAIT_TIME_MS):
			FreeCAD.Console.PrintError("No connection\n")

		message = 'FreeCAD.Console.PrintWarning("Finally\\n")\n'
		FreeCAD.Console.PrintMessage("Client sending> " + message + "\n")
		block = QByteArray()
		outstr = QDataStream(block, QIODevice.WriteOnly)
		outstr.setVersion(QDataStream.Qt_4_0)
		outstr.writeUInt16(0)
		outstr.writeQString(message)
		outstr.device().seek(0)
		outstr.writeUInt16(block.size() - 2)

		self.tcpSocket.write(block)
		if not self.tcpSocket.waitForBytesWritten(msecs=WAIT_TIME_MS):
			FreeCAD.Console.PrintError("Bytes not written\n")

		self.tcpSocket.readyRead.connect(self.dealCommunication)
		self.tcpSocket.error.connect(self.displayError)


	def dealCommunication(self):
		instr = QDataStream(self.tcpSocket)
		instr.setVersion(QDataStream.Qt_4_0)
		if self.blockSize == 0:
			if self.tcpSocket.bytesAvailable() < 2:
				return
			self.blockSize = instr.readUInt16()
		
		if self.tcpSocket.bytesAvailable() < self.blockSize:
			return
		
		FreeCAD.Console.PrintMessage("Client received> " + instr.readString() + "\n")
		
	def displayError(self, socketError):
		if socketError == QAbstractSocket.RemoteHostClosedError:
			pass
		else:
			FreeCAD.Console.PrintError("The following error occurred: %s." % \
									   self.tcpSocket.errorString() + "\n")




def send_request(host, port, command, wait_time=WAIT_TIME_MS):
	tcpSocket = QTcpSocket()
	blockSize = 0
	tcpSocket.connectToHost(host, port, QIODevice.ReadWrite)
	if not tcpSocket.waitForConnected(msecs=wait_time):
		print("sending request> No connection made.")
		return
	print("sending request> request: " + command)
	block = QByteArray()
	outstr = QDataStream(block, QIODevice.WriteOnly)
	outstr.setVersion(QDataStream.Qt_4_0)
	outstr.writeUInt16(0)
	outstr.writeQString(command)
	outstr.device().seek(0)
	outstr.writeUInt16(block.size() - 2)
	tcpSocket.write(block)
	if not tcpSocket.waitForBytesWritten(msecs=wait_time):
		print("sending request> Bytes not written.")
		return
	if not tcpSocket.waitForReadyRead(msecs=10000):
		print("sending request> No response received.")
		return
	instr = QDataStream(tcpSocket)
	instr.setVersion(QDataStream.Qt_4_0)
	if blockSize == 0:
		if tcpSocket.bytesAvailable() < 2:
			return
		blockSize = instr.readUInt16()
	if tcpSocket.bytesAvailable() < blockSize:
		return
	print("sending request> response: " + instr.readString())