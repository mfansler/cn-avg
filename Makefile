PREFIX = ~/.local
export BIN_DIR = ${PWD}/bin
export LIB_DIR = ${PWD}/lib
export SONLIB_DIR = ${PWD}/../sonLib
export PINCHES_DIR = ${PWD}/../pinchesAndCacti

default:
	mkdir -p ${BIN_DIR}
	mkdir -p ${LIB_DIR}
	cd src && make
	cd bin && chmod 755 *

install:
	cp ${BIN_DIR}/* ${PREFIX}/bin
	cp ${LIB_DIR}/* ${PREFIX}/lib

clean:
	rm ${BIN_DIR}/*
	rm ${LIB_DIR}/*

doc: cnavg
	epydoc --graph all --no-private --html --output doc/html cnavg
