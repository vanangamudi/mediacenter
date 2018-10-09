#include <stdio.h>
#include <time.h>


int main(int argc, char *argv[]) {
    struct timespec spec;
    FILE *file;

    clock_gettime(CLOCK_REALTIME, &spec);

    file = fopen("/var/run/keys", "w+");
    fprintf(file, "%s\n%ld", argv[1], spec.tv_nsec);
    fclose(file);
}