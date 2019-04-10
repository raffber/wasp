#include <QApplication>

#include "qtmain.h"
#include <iostream>

TestObject::TestObject() : QObject(0) {
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    std::cout << "hello from qt" << std::endl;
    TestObject stuff;
    return 0;
}