(function () {
    return function e(t, n, r) {
        function i(a, s) {
            if (!n[a]) {
                if (!t[a]) {
                    var u = "function" == typeof require && require;
                    if (!s && u)return u(a, !0);
                    if (o)return o(a, !0);
                    var l = new Error("Cannot find module '" + a + "'");
                    throw l.code = "MODULE_NOT_FOUND", l
                }
                var c = n[a] = {exports: {}};
                t[a][0].call(c.exports, function (e) {
                    var n = t[a][1][e];
                    return i(n ? n : e)
                }, c, c.exports, e, t, n, r)
            }
            return n[a].exports
        }

        for (var o = "function" == typeof require && require, a = 0; a < r.length; a++)i(r[a]);
        return i
    }({
        1: [function (e, t, n) {
            "use strict";
            function r(e) {
                return e && e.__esModule ? e : {"default": e}
            }

            function i(e, t) {
                if (!(e instanceof t))throw new TypeError("Cannot call a class as a function")
            }

            function o(e, t) {
                if ("function" != typeof t && null !== t)throw new TypeError("Super expression must either be null or a function, not " + typeof t);
                e.prototype = Object.create(t && t.prototype, {
                    constructor: {
                        value: e,
                        enumerable: !1,
                        writable: !0,
                        configurable: !0
                    }
                }), t && (Object.setPrototypeOf ? Object.setPrototypeOf(e, t) : e.__proto__ = t)
            }

            var a = function () {
                function e(e, t) {
                    for (var n = 0; n < t.length; n++) {
                        var r = t[n];
                        r.enumerable = r.enumerable || !1, r.configurable = !0, "value" in r && (r.writable = !0), Object.defineProperty(e, r.key, r)
                    }
                }

                return function (t, n, r) {
                    return n && e(t.prototype, n), r && e(t, r), t
                }
            }(), s = function (e, t, n) {
                for (var r = !0; r;) {
                    var i = e, o = t, a = n;
                    s = l = u = void 0, r = !1, null === i && (i = Function.prototype);
                    var s = Object.getOwnPropertyDescriptor(i, o);
                    if (void 0 !== s) {
                        if ("value" in s)return s.value;
                        var u = s.get;
                        return void 0 === u ? void 0 : u.call(a)
                    }
                    var l = Object.getPrototypeOf(i);
                    if (null === l)return void 0;
                    e = l, t = o, n = a, r = !0
                }
            }, u = e("../common/util"), l = r(u), c = e("../common/postmessage"), f = r(c), d = function (e) {
                function t() {
                    i(this, t), s(Object.getPrototypeOf(t.prototype), "constructor", this).call(this), this._data = this._parseInitData(), this._host = window.parent, this._hostModules = {}, this._eventHandlers = {}, this._pendingCallbacks = {}, this._setupAPI(this._data.api), this._messageHandlers = {
                        resp: this._handleResponse,
                        evt: this._handleEvent
                    }, window.addEventListener("DOMContentLoaded", l["default"]._bind(this, this._sendInit))
                }

                return o(t, e), a(t, [{
                    key: "_parseInitData", value: function (e) {
                        try {
                            return JSON.parse(e || window.name)
                        } catch (t) {
                            return {}
                        }
                    }
                }, {
                    key: "_createModule", value: function (e, t) {
                        var n = this;
                        return Object.getOwnPropertyNames(t).reduce(function (t, r) {
                            return t[r] = n._createMethodHandler({mod: e, fn: r}), t
                        }, {})
                    }
                }, {
                    key: "_setupAPI", value: function (e) {
                        var t = this;
                        this._hostModules = Object.getOwnPropertyNames(e).reduce(function (n, r) {
                            return n[r] = t._createModule(r, e[r]), n
                        }, {}), Object.getOwnPropertyNames(this._hostModules._globals || {}).forEach(function (e) {
                            t[e] = t._hostModules._globals[e]
                        })
                    }
                }, {
                    key: "_pendingCallback", value: function (e, t) {
                        this._pendingCallbacks[e] = t
                    }
                }, {
                    key: "_createMethodHandler", value: function (e) {
                        var t = function () {
                            var t = void 0, n = l["default"].argumentsToArray(arguments);
                            l["default"].hasCallback(n) && (t = l["default"].randomString(), this._pendingCallback(t, n.pop())), this._host.postMessage({
                                eid: this._data.extension_id,
                                type: "req",
                                mid: t,
                                mod: e.mod,
                                fn: e.fn,
                                args: n
                            }, this._data.origin)
                        };
                        return l["default"]._bind(this, t)
                    }
                }, {
                    key: "_handleResponse", value: function (e) {
                        var t = e.data, n = this._pendingCallbacks[t.mid];
                        n && (delete this._pendingCallbacks[t.mid], n.apply(window, t.args))
                    }
                }, {
                    key: "_handleEvent", value: function (e) {
                        var t = function () {
                            var t = l["default"].argumentsToArray(arguments);
                            e.source.postMessage({
                                eid: this._data.extension_id,
                                mid: e.data.mid,
                                type: "resp",
                                args: t
                            }, this._data.origin)
                        };
                        t = l["default"]._bind(this, t);
                        var n = e.data, r = this._eventHandlers[n.etyp];
                        r ? r(n.evnt, t) : n.mid && t()
                    }
                }, {
                    key: "_checkOrigin", value: function (e) {
                        return e.origin === this._data.origin && e.source === this._host
                    }
                }, {
                    key: "_sendInit", value: function () {
                        this._host.postMessage({eid: this._data.extension_id, type: "init"}, this._data.origin)
                    }
                }, {
                    key: "require", value: function (e, t) {
                        var n = this, r = Array.isArray(e) ? e : [e], i = r.map(function (e) {
                            return n._hostModules[e]
                        });
                        t.apply(window, i)
                    }
                }, {
                    key: "register", value: function (e) {
                        this._eventHandlers = e || {}, this._host.postMessage({
                            eid: this._data.extension_id,
                            type: "event_query",
                            args: Object.getOwnPropertyNames(e)
                        }, this._data.origin)
                    }
                }]), t
            }(f["default"]);
            t.exports = new d
        }, {"../common/postmessage": 2, "../common/util": 3}], 2: [function (e, t, n) {
            "use strict";
            function r(e) {
                return e && e.__esModule ? e : {"default": e}
            }

            function i(e, t) {
                if (!(e instanceof t))throw new TypeError("Cannot call a class as a function")
            }

            var o = function () {
                function e(e, t) {
                    for (var n = 0; n < t.length; n++) {
                        var r = t[n];
                        r.enumerable = r.enumerable || !1, r.configurable = !0, "value" in r && (r.writable = !0), Object.defineProperty(e, r.key, r)
                    }
                }

                return function (t, n, r) {
                    return n && e(t.prototype, n), r && e(t, r), t
                }
            }(), a = e("./util"), s = r(a), u = function () {
                function e(t) {
                    i(this, e);
                    var n = t || {};
                    this._registerListener(n.listenOn)
                }

                return o(e, [{
                    key: "_registerListener", value: function (e) {
                        e && e.addEventListener || (e = window), e.addEventListener("message", s["default"]._bind(this, this._receiveMessage), !1)
                    }
                }, {
                    key: "_receiveMessage", value: function (e) {
                        var t = e.data.eid, n = void 0;
                        if (t && this._registeredExtensions && (n = this._registeredExtensions[t]), !this._checkOrigin(e, n))return !1;
                        var r = this._messageHandlers[e.data.type];
                        r && r.call(this, e, n)
                    }
                }]), e
            }();
            t.exports = u
        }, {"./util": 3}], 3: [function (e, t, n) {
            "use strict";
            function r(e, t) {
                if (!(e instanceof t))throw new TypeError("Cannot call a class as a function")
            }

            var i = function () {
                function e(e, t) {
                    for (var n = 0; n < t.length; n++) {
                        var r = t[n];
                        r.enumerable = r.enumerable || !1, r.configurable = !0, "value" in r && (r.writable = !0), Object.defineProperty(e, r.key, r)
                    }
                }

                return function (t, n, r) {
                    return n && e(t.prototype, n), r && e(t, r), t
                }
            }(), o = function () {
                function e() {
                    r(this, e)
                }

                return i(e, [{
                    key: "randomString", value: function () {
                        return Math.floor(1e9 * Math.random()).toString(16)
                    }
                }, {
                    key: "argumentsToArray", value: function (e) {
                        for (var t = [], n = 0; n < e.length; n++)t.push(e[n]);
                        return t
                    }
                }, {
                    key: "hasCallback", value: function (e) {
                        var t = e.length;
                        return t > 0 && "function" == typeof e[t - 1]
                    }
                }, {
                    key: "_bind", value: function (e, t) {
                        return Function.prototype.bind ? t.bind(e) : function () {
                            return t.apply(e, arguments)
                        }
                    }
                }]), e
            }();
            t.exports = new o
        }, {}]
    }, {}, [1])(1)
});