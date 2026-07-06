[app]

title = Ayson V15
package.name = aysonv15
package.domain = org.ayson

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.5

requirements = python3,kivy,certifi

orientation = portrait

fullscreen = 0

android.permissions = INTERNET

android.accept_sdk_license = True
android.api = 35
android.minapi = 28
android.ndk = 25b
android.archs = arm64-v8a

p4a.branch = master

[buildozer]

log_level = 2
warn_on_root = 1
