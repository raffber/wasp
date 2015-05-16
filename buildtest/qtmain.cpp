#include <QApplication>

#include "qtmain.h"

TestObject::TestObject() : QObject(0) {
}

int main() {
    QApplication app();
    stuff = TestObject();
    app.exec();
}