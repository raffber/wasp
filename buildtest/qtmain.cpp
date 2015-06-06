#include <QApplication>

#include "qtmain.h"

TestObject::TestObject() : QObject(0) {
}

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    TestObject stuff;
    app.exec();
}