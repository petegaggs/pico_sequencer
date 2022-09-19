# midi sequencer for raspberry pi pico
from machine import Pin, UART, Timer
import ustruct

clk_a_pin = Pin(15, Pin.IN, Pin.PULL_UP)
rst_a_pin = Pin(14, Pin.IN, Pin.PULL_UP)
rec_mode_sw_pin = Pin(13, Pin.IN, Pin.PULL_UP)

midi_0 = machine.UART(0,31250)
midi_1 = machine.UART(1,31250)
midi_out = [midi_0, midi_1]

def note_on(note, velocity=127, port=0):
    midi_out[port].write(ustruct.pack("bbb",0x90,note,velocity))
    
def note_off(note, port=0):
    note_on(note, velocity=0, port=port)

def read_midi_in():
    # simple midi receiver. respond to channel 0 only. return note number for note on command
    retval = False # default
    if (midi_0.any()):
        global midi_in_msg_byte, midi_in_status, midi_in_note, midi_in_status
        msg = midi_0.read(1)[0]
        if msg in [0x80, 0x90]: # status
            if msg == 0x90:
                midi_in_status = "note_on"
            elif msg == 0x80:
                midi_in_status = "note_off"
            midi_in_msg_byte = 0
        elif (msg & 0x80) == 0:
            if midi_in_msg_byte == 0:
                midi_in_note = msg
                midi_in_msg_byte += 1
            else:
                midi_in_vel = msg
                if midi_in_status == "note_on" and midi_in_vel > 0:
                    note_on(midi_in_note)
                    retval = midi_in_note
                else:
                    note_off(midi_in_note)
                midi_in_msg_byte = 0
    return retval

rec_mode = last_rec_mode = False
sequence = [32, 44, 56, 68, 56, 44, 36, 32]
step = 0

wait_play_mode = False # default

def check_switches(void):
    global rec_mode
    rec_mode = True if rec_mode_sw_pin.value() == 0 else False

timer = Timer(-1)
timer.init(period=100, mode=Timer.PERIODIC, callback=check_switches)

last_clk_a = 0
current_note = None

def save_sequence_to_flash(sequence_data):
    print("save to flash")
    seq_file = open("seq_data", "w")
    for n in sequence_data:
        seq_file.write("{}\n".format(n))
    seq_file.close()

def load_sequence_from_file(file):
    seq = []
    for line in file:
        seq.append(int(line))
    return seq

try:
    a_file = open("seq_data", "r")
    print("file found")
    sequence = load_sequence_from_file(a_file)
    print("seq: {}".format(sequence))
except:
    print("could not open file")
    save_sequence_to_flash(sequence)

while True:
    clk_a_posedge = clk_a_negedge = False # default
    rec_note = read_midi_in()
    clk_a = 1 - clk_a_pin.value() # signal is active low, invert it here
    if clk_a != last_clk_a:
        if clk_a == 1:
            clk_a_posedge = True
        else:
            clk_a_negedge = True
        last_clk_a = clk_a
    if rec_mode != last_rec_mode:
        print("change to {}".format(rec_mode))
        if not rec_mode:
            wait_play_mode = True
            save_sequence_to_flash(sequence)
        else:
            step = 0
            if current_note != None:
                note_off(current_note)
                current_note = None
        last_rec_mode = rec_mode
    if not rec_mode:
        # playback
        if clk_a_posedge:
            if rst_a_pin.value() == 0:
                step = 0
                if wait_play_mode:
                    wait_play_mode = False # ok to start now
            if not wait_play_mode:
                current_note = sequence[step]
                note_on(current_note)
            clk_a_posedge = False
        if clk_a_negedge:
            if current_note != None:
                note_off(current_note)
                current_note = None
            step += 1
            if step == 8:
                step = 0
                wait_play_mode = False # allow case where no reset is used
            clk_a_negedge = False
    else:
        # record mode
        if rec_note:
            print("rec step {} note {}".format(step, rec_note))
            sequence[step] = rec_note
            step += 1
            if step == 8:
                step = 0
