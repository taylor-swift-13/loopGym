// Source: data/benchmarks/code2inv/91.c

void loopy_329(void){

    int x = 0;
    int y = 0;

    while(y >= 0){
        y = y + x;
    }

    {;
//@ assert( y>= 0);
}

}