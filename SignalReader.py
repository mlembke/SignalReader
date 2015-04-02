#!/usr/bin/env python
 # -*- coding: utf-8 -*-
import numpy as np
from PyQt4 import QtGui, QtCore
from PyQt4.Qt import QSize, QPoint
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
import serial

class Button(QtGui.QToolButton):
    def __init__(self, text, parent = None):
        super(Button, self).__init__(parent)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding,
                QtGui.QSizePolicy.Preferred)
        self.setText(text)
 
    def sizeHint(self):
        size = super(Button, self).sizeHint()
        size.setHeight(size.height() + 20)
        size.setWidth(max(size.width(), size.height()))
        return size
    
class GUI(QtGui.QDialog):
    def __init__(self):
        super(GUI, self).__init__()
        # Pola pomocnicze do obsługi pętli
        self._generator = None
        self._timerId = None
        
        # Właściwe pola klasy
        self.serial = serial.Serial()
        self.data = np.array([[], [], []])
        self.frames = 0;
        self.last_frame = 0;
        self.frames_lost = 0;
        self.window = 100  # Szerokość okna rysowanego sygnału
        
        # Ustawienia ramki
        self.frame_length = 30;  # Długość ramki z danymi
        self.frame_markers = np.array([int('A5', 16), int('5a', 16)])
        self.buffer = bytearray(self.frame_length - len(self.frame_markers))
        
        # Elementy okna
        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumSize(self.canvas.size())
                                   
        self.serial_line = QtGui.QLineEdit(self)
        self.serial_line.setText('COM9')
        self.serial_line.setAlignment(QtCore.Qt.AlignCenter)
        self.serial_line.setMaxLength(30)
        
        self.serial_line_label = QtGui.QLabel("Port")
        self.serial_line_label.setAlignment(QtCore.Qt.AlignCenter)
        
        self.lost_frames_count = QtGui.QLineEdit(self)
        self.lost_frames_count.setText('0%')
        self.lost_frames_count.setAlignment(QtCore.Qt.AlignCenter)
        self.lost_frames_count.setMaxLength(30)
        
        self.lost_frames_label = QtGui.QLabel("Frames lost")
        self.lost_frames_label.setAlignment(QtCore.Qt.AlignCenter)
        
        self.start_button = self.createButton("Start", self.start)
        self.stop_button = self.createButton("Stop", self.stop)
        self.stop_button.setEnabled(False)
        
        self.info_line = QtGui.QLineEdit(self)
        self.info_line.setReadOnly(True)
        self.info_line.setAlignment(QtCore.Qt.AlignCenter)
        self.info_line.setMaxLength(30)
        self.info_line.setText('INFO')
        
        self.setWindowTitle('Signal Reader v.1.0')
        # Układanie layout'u
        layout = QtGui.QGridLayout()
        layout.setSizeConstraint(QtGui.QLayout.SetFixedSize)
        layout
        layout.addWidget(self.canvas, 0, 0, 1, 2)
        layout.addWidget(self.serial_line_label, 1, 0, 1, 2)
        layout.addWidget(self.serial_line, 2, 0, 1, 2)
        layout.addWidget(self.start_button, 3, 0, 1, 1)
        layout.addWidget(self.stop_button, 3, 1, 1, 1)
        layout.addWidget(self.lost_frames_label, 4, 0, 1, 2)
        layout.addWidget(self.lost_frames_count, 5, 0, 1, 2)
        layout.addWidget(self.info_line, 6, 0, 1, 2)
        self.setLayout(layout)
        self.setFigures()
    
    def setFigures(self):
        self.channel1 = self.figure.add_subplot(3, 1, 1)
        self.channel1.hold(True)
        self.channel1_data, = self.channel1.plot(np.zeros(self.window))
        plt.ylim([0, 4096])
        plt.title('Channel 1')
        plt.grid()
        plt.tight_layout(pad = 0.4, w_pad = 0.5, h_pad = 1.0)
        
        self.channel2 = self.figure.add_subplot(3, 1, 2)
        self.channel2.hold(True)
        self.channel2_data, = self.channel2.plot(np.zeros(self.window))
        plt.ylim([0, 4096])
        plt.title('Channel 2')
        plt.grid()
        plt.tight_layout(pad = 0.4, w_pad = 0.5, h_pad = 1.0)
        
        self.channel3 = self.figure.add_subplot(3, 1, 3)
        self.channel3.hold(True)
        self.channel3_data, = self.channel3.plot(np.zeros(self.window))
        plt.ylim([0, 4096])
        plt.title('Channel 3')
        plt.grid()
        plt.tight_layout(pad = 0.4, w_pad = 0.5, h_pad = 1.0)
        
        plt.ion()
        
    def start(self):
        # Aktywancja/deazktywacja przycisków
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.port = str(self.serial_line.text())  # Zapisuje nazwę portu
        if self._timerId is not None:
            self.killTimer(self._timerId)
        self.serial_line.setReadOnly(True)  # Ustawia pole z portem na niezmienialne
        self._generator = self.readData()  # Wchodzi do pętli wczytywania danych
        self._timerId = self.startTimer(0)
        
    def stop(self):
        # Aktywancja/deazktywacja przycisków
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        if self._timerId is not None:
            self.killTimer(self._timerId)
        self._generator = None
        self._timerId = None
        self.serial_line.setReadOnly(False)
        if(self.serial.isOpen()):
            self.serial.close()
            self.info_line.setText('STOP')
            
    def readData(self):
        ''' Metoda do czytania dancyh z podanego portu. '''
        try:
            self.serial = serial.Serial(self.port)  # Otwiera port
            self.info_line.setText('Reading data...')  # Zmienia napis
            while (True):
                input = self.serial.read()  # Czyta 1 bajt
                # Sprawdzenie czy jest starszym bajtem znacznika
                if(int.from_bytes(input, byteorder = 'big') == self.frame_markers[0]):
                    # Czytanie kolejnego 1 bajtu
                    input = self.serial.read()
                    # Sprawdzenie czy następny jest młodszym bajtem znacznika
                    if(int.from_bytes(input, byteorder = 'big') == self.frame_markers[1]):
                        # Jeśli tak to znaczy, że mamy ramkę
                        self.frames += 1
                        # Wczytujemy do struktury buffer (która jest tablicą
                        # bajtów) 28 bajtów (bo taki został ustalony jej rozmiar)
                        self.serial.readinto(self.buffer)
                        # Zamiana tablicy bajtów na macierz liczb całkowitych
                        self.buffer = np.array(self.buffer, dtype = np.int32);
                        self.parseData()
                        self.plot()
                        self.buffer = bytearray(self.frame_length - 2)
                    yield
        except serial.SerialException as ex:
            self.info_line.setText('Can\'t open the serial port!')
            
    def parseData(self):
        ''' Metoda analizująca pobraną ramkę z danymi. '''
        if(self.last_frame == 0):
            self.last_frame = self.buffer[0] * 256 + self.buffer[1]
        else:
            frame = self.buffer[0] * 256 + self.buffer[1]
            if(frame - 1 != self.last_frame):
                self.frames_lost += 1
            self.last_frame = frame
            
        self.lost_frames_count.setText(str(round(self.frames_lost / self.frames * 100, 2)) + '%')
            
        # Sprawdzanie sumy kontrolnej
        checksum = self.buffer[-2] * 256 + self.buffer[-1]
        sum = np.sum(self.buffer[:-2])
        #-----------------------------------------------------------------------
        # Tutaj w warunku ustawić sum == checksum
        #-----------------------------------------------------------------------
        if(True):
            self.buffer = self.buffer[2:-2].reshape((-1, 2))
            self.buffer[:, 0] *= 256
            self.buffer = np.sum(self.buffer, 1)
            self.buffer = self.buffer.reshape((-1, 3)).T
            self.data = np.hstack((self.data, self.buffer))
            
    def plot(self):
        if(self.data.shape[1] >= self.window):
            self.data = self.data[:, -self.window:]
            self.channel1_data.set_ydata(self.data[0])
            self.channel2_data.set_ydata(self.data[1])
            self.channel3_data.set_ydata(self.data[2])
            self.canvas.draw()
        
    def timerEvent(self, event):
        if self._generator is None:
            return
        try:
            next(self._generator)
        except StopIteration:
            self.stop()
            
    def closeEvent(self, event):
        self.stop()
        event.accept()
        
    def createButton(self, text, member):
        button = Button(text)
        button.clicked.connect(member)
        return button
    
if __name__ == '__main__':
    import sys
    app = QtGui.QApplication(sys.argv)
    window = GUI()
    sys.exit(window.exec_())
