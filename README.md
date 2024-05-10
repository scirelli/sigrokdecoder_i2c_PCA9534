# PCA9534 Decoder

### Custom Decoder
## Linux
To run your custom decode set the `SIGROKDECODE_DIR` to point to your decoders dir.
```
SIGROKDECODE_DIR=/path/to/libsigrokdecode/decoders/ pulseview
```
## Mac
```
mkdir -p ~/.local/share/libsigrokdecode/
ln -s <project location>/sigrokdecoder_i2c_PCA9534/src ~/.local/share/libsigrokdecode/decoders
```

### Debug
In your init add
```
def __init__(self):
    import rpdb2
    rpdb2.start_embedded_debugger("password", fAllowRemote=True, timeout=50000000)
```
Run `rdb2` in a terminal.
<br/>
Once running setup the password
```
password "password"
```
Go back to PulseView and run the decoder. Switch back to console and type
```
attach
```
It will list the process ids of the running scripts. Pick yours and attach again
```
attach 7722
```

### References
* https://stackoverflow.com/questions/12367183/rpdb2-how-to-connect-to-a-pid
