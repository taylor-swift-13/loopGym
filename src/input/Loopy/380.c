// Source: data/benchmarks/sv-benchmarks/loop-lit/jm2006_variant.c
#define LARGE_INT 1000000
extern int unknown_int(void);

/*@
  requires i >= 0 && i <= LARGE_INT;
  requires j >= 0;
*/
void loopy_380(int i, int j) {

    
    
    int x = i;
    int y = j;
    int z = 0;
    while(x != 0) {
        x --;
        y -= 2;
        z ++;
    }
    if (i == j) {
        {;
//@ assert(y == -z);
}

    }
    return;
}