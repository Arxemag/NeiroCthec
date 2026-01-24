"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RefreshAuthGuard = exports.AccessAuthGuard = void 0;
const passport_1 = require("@nestjs/passport");
class AccessAuthGuard extends (0, passport_1.AuthGuard)('jwt-access') {
}
exports.AccessAuthGuard = AccessAuthGuard;
class RefreshAuthGuard extends (0, passport_1.AuthGuard)('jwt-refresh') {
}
exports.RefreshAuthGuard = RefreshAuthGuard;
//# sourceMappingURL=guards.js.map