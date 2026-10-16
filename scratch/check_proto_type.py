with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    f.seek(32057000)
    data = f.read(2000)

# Decode protobuf FieldDescriptorProto
# Wire format in FileDescriptorProto:
# Tag 2 (name), Tag 3 (number), Tag 4 (label), Tag 5 (type)
# Let's inspect bytes around warning_trigger_countdown
pos = data.find(b'warning_trigger_countdown')
print('pos:', pos)
print('bytes before and after:', data[pos-20:pos+50])
