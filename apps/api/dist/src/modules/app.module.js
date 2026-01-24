"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppModule = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const prisma_module_1 = require("./prisma/prisma.module");
const auth_module_1 = require("./auth/auth.module");
const users_module_1 = require("./users/users.module");
const voices_module_1 = require("./voices/voices.module");
const projects_module_1 = require("./projects/projects.module");
const audios_module_1 = require("./audios/audios.module");
const subscription_module_1 = require("./subscription/subscription.module");
const health_module_1 = require("./health/health.module");
const storage_module_1 = require("./storage/storage.module");
const jobs_module_1 = require("./jobs/jobs.module");
let AppModule = class AppModule {
};
exports.AppModule = AppModule;
exports.AppModule = AppModule = __decorate([
    (0, common_1.Module)({
        imports: [
            config_1.ConfigModule.forRoot({ isGlobal: true }),
            prisma_module_1.PrismaModule,
            storage_module_1.StorageModule,
            jobs_module_1.JobsModule,
            auth_module_1.AuthModule,
            users_module_1.UsersModule,
            voices_module_1.VoicesModule,
            projects_module_1.ProjectsModule,
            audios_module_1.AudiosModule,
            subscription_module_1.SubscriptionModule,
            health_module_1.HealthModule,
        ],
    })
], AppModule);
//# sourceMappingURL=app.module.js.map