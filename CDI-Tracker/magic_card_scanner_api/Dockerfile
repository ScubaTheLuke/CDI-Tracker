FROM gradle:jdk11 as GRADLE_BUILD
COPY . /home/gradle/src
WORKDIR /home/gradle/src
RUN gradle build

FROM openjdk:11-jre-slim
COPY --from=GRADLE_BUILD /home/gradle/src/build/libs/*.jar /app/magic-card-scanner-api.jar/
WORKDIR /app
ENTRYPOINT ["java", "-jar", "magic-card-scanner-api.jar"]