// Source: data/benchmarks/sv-benchmarks/loop-new/count_by_nondet.c
#define LARGE_INT 1000000
extern int unknown_int(void);

void loopy_385(void) {
    int i = 0;
    int k = 0;
    while(i < LARGE_INT) {
        int j = unknown_int();
        if (!(1 <= j && j < LARGE_INT)) return;
        i = i + j;
        k ++;
    }
    {;
//@ assert(k <= LARGE_INT);
}

    return;
}