[app]

title = Ayson
package.name = ayson
package.domain = org.ayson

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy

orientation = portrait

fullscreen = 0

android.permissions = INTERNET

android.api = 35
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

p4a.branch = master

[buildozer]

log_level = 2
warn_on_root = 1
