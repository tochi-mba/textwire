package com.rextechnologies.textwire.protocol

// The fixed numbers of protocol version 1. protocol/PROTOCOL.md section 2 explains each one, and
// protocol/vectors/ids.json pins them; the vector tests check both agree.

/** The version nibble every v1 frame carries. */
const val FRAME_VERSION = 1

/** The most characters a single GSM-7 SMS holds, and so the most a frame's text may have. */
const val FRAME_CHARS = 160

/** The most bytes a frame decodes to: 160 base64url characters of 6 bits. */
const val FRAME_BYTES = 120

/** Version and type, tag, sequence, total, CRC. */
const val HEADER_BYTES = 6

/** Payload bytes one frame carries. */
const val BODY_BYTES = FRAME_BYTES - HEADER_BYTES

/** The most frames one response can have. */
const val MAX_FRAMES = 255
